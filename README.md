# 技术文章摘抄保存

## 数据来源

+ [learn.lianglianglee.com](https://learn.lianglianglee.com)
+ [GitHub 仓库](https://github.com/zhwei820/learn.lianglianglee.com)

## 预览效果

+ [Git Pages](https://jint233.github.io/)

## 项目启动&部署方式

### 环境安装

```shell
# 自动创建 .venv，并安装 requirements.txt 中锁定的版本
make setup
```

### 本地启动

```shell
# 仅预览门户首页（不会构建各技术模块）
make serve MODULE=portal

# 构建后的完整站点预览（默认 http://127.0.0.1:8000）
make preview
```

### 按模块构建与预览

一级目录已拆分为独立的 MkDocs 构建模块。构建脚本会自动扫描 `docs/` 下的一级目录并动态生成运行配置；新增目录后直接执行构建或预览命令即可，无需维护 YAML、模块列表或 CI 配置。

```shell
# 构建全部模块（按一级模块数量自动并发，最多 20 个）
make build

# 构建全部模块并启动完整站点预览
make serve

# 手动调整并发数（超过 20 时自动限制为 20）
make build JOBS=6

# 只构建或预览 Java 模块
make build MODULE=Java
make serve MODULE=Java
```

可通过 `./scripts/module-configs.sh list` 查看当前模块。`make preview` 提供已构建的完整站点；`make serve` 会先构建完整站点再启动预览。`make serve MODULE=Java` 会同时预览首页和 `/Java/` 模块路径，并支持 MkDocs 热更新。

### Docker部署

+ 使用 Dockerfile 生成镜像；可通过 `MODULES=Java docker compose build` 只渲染指定模块
+ 使用 docker-compose 脚本启动服务
  
#### Github Pages

使用 .github/workflows/ci.yml

## 项目搭建

项目基于 [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/getting-started/) 构建，相关配置可在官网查阅

### 👇👇👇👇👇👇

如果有帮到您的话，请帮忙点个 Star~ Thanks♪(･ω･)ﾉ
