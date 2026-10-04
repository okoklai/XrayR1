#!/usr/bin/env bash
set -Eeuo pipefail

# Assets come from this repository, or an existing local clone.
REPOSITORY="okoklai/XrayR1"
RAW_BASE="https://raw.githubusercontent.com/${REPOSITORY}/master"
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
LOCAL_REPO=""
if [[ -f "$SCRIPT_DIR/VERSION" && -d "$SCRIPT_DIR/dist" ]]; then
    LOCAL_REPO="$SCRIPT_DIR"
fi

die() { echo "错误：$*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || die "请使用 root 运行。"
[[ $(uname -s) == Linux ]] || die "仅支持 Linux。"
command -v systemctl >/dev/null || die "需要 systemd；容器请使用 Docker 部署。"
case "$(uname -m)" in
    x86_64|amd64) arch=64 ;;
    aarch64|arm64) arch=arm64-v8a ;;
    s390x) arch=s390x ;;
    *) die "不支持的架构：$(uname -m)" ;;
esac

if ! command -v curl >/dev/null || ! command -v unzip >/dev/null || ! command -v sha256sum >/dev/null; then
    if command -v apt-get >/dev/null; then
        apt-get update
        apt-get install -y ca-certificates curl unzip coreutils
    elif command -v dnf >/dev/null; then
        dnf install -y ca-certificates curl unzip coreutils
    elif command -v yum >/dev/null; then
        yum install -y ca-certificates curl unzip coreutils
    else
        die "请先安装 ca-certificates、curl、unzip 和 coreutils。"
    fi
fi

stage=$(mktemp -d)
trap 'rm -rf -- "$stage"' EXIT
fetch() {
    local path=$1 output=$2
    if [[ -n "$LOCAL_REPO" ]]; then
        cp -- "$LOCAL_REPO/$path" "$output"
    else
        curl --fail --show-error --location --retry 3 --connect-timeout 15 \
            "$RAW_BASE/$path" --output "$output"
    fi
}

version=${1:-}
if [[ -z "$version" ]]; then
    fetch VERSION "$stage/VERSION"
    version=$(tr -d '\r\n' < "$stage/VERSION")
fi
[[ "$version" == v* ]] || version="v$version"
[[ "$version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+([.-][a-zA-Z0-9.-]+)?$ ]] || die "无效版本号。"
asset="XrayR-linux-${arch}.zip"
echo "从 ${REPOSITORY} 安装 ${version} (${arch})"
# Download and verify everything before touching an existing installation.
fetch "dist/$version/$asset" "$stage/$asset" || die "本仓库尚未备份该版本/架构。现有安装未改动。"
fetch "dist/$version/SHA256SUMS" "$stage/SHA256SUMS"
awk -v name="$asset" '$2 == name {print}' "$stage/SHA256SUMS" > "$stage/selected.sha256"
[[ $(wc -l < "$stage/selected.sha256") -eq 1 ]] || die "缺少唯一的 SHA256 校验值。"
(cd "$stage" && sha256sum --check selected.sha256)
unzip -tq "$stage/$asset"
mkdir "$stage/unpacked"
unzip -q "$stage/$asset" -d "$stage/unpacked"
[[ -s "$stage/unpacked/XrayR" ]] || die "压缩包缺少 XrayR。"
chmod +x "$stage/unpacked/XrayR"
"$stage/unpacked/XrayR" version || die "程序无法运行；amd64 包需要 glibc 2.34+，可使用 Debian 12+ 或 Docker。现有安装未改动。"
fetch XrayR.service "$stage/XrayR.service"
fetch XrayR.sh "$stage/XrayR.sh"
[[ -s "$stage/XrayR.sh" ]] || die "管理脚本为空。"
bash -n "$stage/XrayR.sh"
[[ -s "$stage/XrayR.service" ]] || die "服务文件为空。"

mkdir -p /usr/local/XrayR /etc/XrayR
if [[ -f /etc/systemd/system/XrayR.service ]]; then
    systemctl stop XrayR
fi
install -m 755 "$stage/unpacked/XrayR" /usr/local/XrayR/XrayR.new
mv -f /usr/local/XrayR/XrayR.new /usr/local/XrayR/XrayR
fresh=0
[[ -f /etc/XrayR/config.yml ]] || fresh=1
for file in config.yml dns.json route.json custom_outbound.json custom_inbound.json rulelist geoip.dat geosite.dat; do
    if [[ ! -e "/etc/XrayR/$file" ]]; then
        install -m 644 "$stage/unpacked/$file" "/etc/XrayR/$file"
    fi
done
install -m 644 "$stage/XrayR.service" /etc/systemd/system/XrayR.service
install -m 755 "$stage/XrayR.sh" /usr/bin/XrayR
ln -sfn /usr/bin/XrayR /usr/bin/xrayr
systemctl daemon-reload
systemctl enable XrayR
if [[ "$fresh" -eq 1 ]]; then
    echo "安装完成。请先编辑 /etc/XrayR/config.yml，再执行 XrayR start。"
else
    systemctl restart XrayR
    sleep 2
    systemctl is-active --quiet XrayR || die "服务未正常启动，请执行 XrayR log 检查配置。"
    echo "更新完成，已有配置和规则文件已保留。"
fi
echo "使用说明：https://github.com/${REPOSITORY}#readme"
