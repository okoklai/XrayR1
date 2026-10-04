# XrayR1：可独立部署的 XrayR 备份

本仓库：<https://github.com/okoklai/XrayR1>。安装、更新、管理脚本和 Docker 构建均使用本仓库保存的文件，不再依赖原作者的代码仓库、Release 或 XrayR 容器镜像。

当前备份版本 **v0.9.5**，支持 Linux **amd64、arm64、s390x**。`dist/v0.9.5/` 直接保存三份原始安装包（总计约 105 MiB），不使用 Git LFS，不需要先创建 Release。`backup/` 保存对应源码、来源和校验记录。保留 MPL-2.0 许可证与上游署名。

## 安装（Linux + systemd）

使用 root 执行。下面命令需要这些修改已经推送到本仓库的 `master` 分支。

备份的 amd64 二进制依赖 glibc 2.34 或更高版本，可使用 Debian 12+、Ubuntu 22.04+。不再承诺旧脚本所列的 CentOS 7、Debian 8 等系统兼容性；旧系统优先使用 Docker。安装器会先执行程序的 `version` 命令检查兼容性，失败时保留原安装。

```bash
curl -fSL --retry 3 https://raw.githubusercontent.com/okoklai/XrayR1/master/install.sh -o /tmp/xrayr1-install.sh && bash /tmp/xrayr1-install.sh
```

指定已备份版本：

```bash
bash /tmp/xrayr1-install.sh v0.9.5
```

也可以复制完整仓库到服务器后使用本地文件安装；已装齐 `ca-certificates`、`curl`、`unzip`、`coreutils` 时，安装不需要访问 GitHub：

```bash
git clone https://github.com/okoklai/XrayR1.git
cd XrayR1
sudo bash install.sh
```

脚本先下载/读取全部安装材料并校验 SHA256，成功后才停止服务、替换程序。不支持的架构或未备份的版本会报错，不会回退到上游下载。升级保留 `/etc/XrayR/` 下已有配置、规则和地理数据库。全新安装不会自动启动示例节点。

## 配置与管理

编辑 `/etc/XrayR/config.yml`，按面板实际设置 `PanelType`、`ApiHost`、`ApiKey`、`NodeID`、`NodeType` 和证书。完整配置示例见 [config/config.yml](config/config.yml)，其余 DNS、路由、自定义入站/出站、规则与地理数据库也在 `config/` 中；它们与备份的程序安装包保持一致。

```bash
XrayR start                 # 配置完成后启动
XrayR stop
XrayR restart
XrayR status
XrayR log
XrayR config
XrayR version
XrayR enable
XrayR disable
XrayR update                # 使用本仓库 VERSION 指定的版本
XrayR update v0.9.5         # 仅限本仓库已经保存的版本
XrayR update_shell          # 从本仓库更新管理脚本
```

`xrayr` 小写命令也可使用。已有旧版管理脚本的机器应先执行上面的新安装命令，之后更新才会使用本仓库。需要离线更新时运行完整本地仓库的 `bash install.sh`；管理菜单更新仍会访问本仓库。

管理菜单的 BBR 选项只启用当前内核已有的 BBR，不再下载第三方脚本或替换内核。如果内核不支持，按提示通过发行版软件源升级。

## Docker Compose（推荐本地构建）

服务器需要 Docker 和 Compose 插件；使用 Linux 主机网络模式。

```bash
git clone https://github.com/okoklai/XrayR1.git
cd XrayR1
# 编辑 config/config.yml 中的面板、节点和证书配置
sudo docker compose up -d --build
sudo docker compose logs -f
```

构建直接解压本仓库 `dist/` 中的安装包并校验 SHA256，不拉取上游 XrayR 镜像，也不下载上游源码。使用 Debian bookworm 基础镜像以满足 amd64 包的 glibc 依赖；基础镜像与 ca-certificates/tzdata 仍使用 Debian 官方资源。

更新：

```bash
git pull --ff-only
sudo docker compose up -d --build
```

`config/` 会挂载到 `/etc/XrayR/`。保留自己的配置备份；若修改过跟踪文件，先处理 Git 提示的本地更改再拉取。容器日志用 Compose 查看，宿主机的 `XrayR` 管理菜单不控制容器。

## 发布本仓库的 Release 和 GHCR 镜像

安装和 Compose 本地构建不依赖以下发布步骤。

1. 把本次全部文件（包括 `dist/` 和 `backup/`）推送到 `master`。
2. 在 GitHub Actions 启用工作流，运行 `Verify standalone distribution` 检查。
3. 手动运行 `Publish local backups and container`。工作流只从本仓库文件生成 Release 附件和三架构镜像，使用自动提供的 `GITHUB_TOKEN`，不需要 Docker Hub 密码。
4. 首次发布后，在 GHCR 包设置中把 `xrayr1` 设为 Public，才能匿名拉取。

发布成功后才可使用：

```bash
docker pull ghcr.io/okoklai/xrayr1:v0.9.5
docker run -d --name xrayr --restart=always --network=host \
  -v "$(pwd)/config:/etc/XrayR" ghcr.io/okoklai/xrayr1:v0.9.5
```

## 备份范围与维护

- [backup/provenance.json](backup/provenance.json)：原始下载地址、源码提交、各文件 SHA256。
- [backup/XrayR-v0.9.5-source.tar.gz](backup/XrayR-v0.9.5-source.tar.gz)：`a9086/XrayR` 标签 `v0.9.5` 的原始源码快照，提交 `ea125e4a4fdb964487df91a6fec03476a57b20ce`。用于审计、许可证要求和后续维护，不参与当前部署。归档内保留原始导入路径和上游工作流以保存原貌，不能直接当成本仓库的发布流程使用。
- [dist/v0.9.5/SHA256SUMS](dist/v0.9.5/SHA256SUMS)：三份安装包校验清单，已与备份时 GitHub Release API 中的 digest 核对。
- [LICENSE](LICENSE)：MPL-2.0。

原项目提供程序与脚本基础，本仓库维护独立分发。来源记录中的上游地址仅用于溯源，运行时不会访问。校验值用于检测传输或存储损坏，不代表对上游二进制做过安全审计或可复现构建验证。

以后添加版本时，先保存三架构压缩包和对应源码，生成 `SHA256SUMS`、更新来源记录及 `config/`，再同步修改 `VERSION`、`Dockerfile` 和 `docker-compose.yml` 的版本。只有已保存的版本才能安装；目前没有备份上游全部历史版本和其他操作系统版本。

本备份解决 XrayR 源仓库/Release/镜像删除导致的部署失效。它不是整个互联网依赖的离线镜像：系统软件源、Debian 基础镜像、GitHub 基础服务仍是外部依赖；源码重新编译仍需 Go 1.24.1 及 `go.mod` 中的第三方依赖。建议另外保存整个仓库和构建后的容器镜像。

## 验证

```bash
bash -n install.sh && bash -n XrayR.sh
python3 -m unittest discover -s tests -v
docker compose config --quiet
docker compose build
docker run --rm --entrypoint XrayR xrayr1:local version
```

CI 会执行离线文件/架构/来源校验、Shell 语法检查、Linux 程序版本检查与 Docker 构建检查。Windows 上的文件校验不能替代 Linux systemd 启动和真实面板连接测试。
