# 进阶：Dockerfile 高阶使用指南及镜像优化

## Dockerfile 高阶使用及新特性解读

通过之前的学习，我们已经知道 Dockerfile 是一种可用于镜像构建，具备特定语法的文本文件。而 Docker 自身在使用此文件进行构建镜像的过程中，遵循其固定的行为。

比如在上次 [Chat](https://gitbook.cn/gitchat/activity/5cd527e864de19331ba79278) 提到的 **缓存** 。

Docker 构建系统中，默认情况下为了加快构建的速度，会将构建过程中的每层都进行缓存，我们建议在编写 Dockerfile 的时候，将更新最为频繁的步骤写到最后面，以避免因为该步骤的内容变更，进而导致后续步骤的缓存失效（缓存的控制是 Docker 固定的行为，我们在之后的 Chat 中会进一步深入内部进行分析）。

而同时，我们通过深入到 Docker 镜像内部，发现了它内部的组织形式，对于镜像而言，它其实是使用配置元信息，将对应内容的层（layer）组织起来的一个集合。

那么在使用 Dockerfile 构建镜像的时候，除了上次 [Chat](https://gitbook.cn/gitchat/activity/5cd527e864de19331ba79278) 聊到的内容外，有哪些值得掌握的高级技巧呢？ 我们来正式开始本次 Chat 。

## 打开 BuildKit 支持

在上次 [Chat](https://gitbook.cn/gitchat/activity/5cd527e864de19331ba79278) 的最后，我们提到可以通过 BuildKit 以提高构建效率，这里我们来对它进行更加详细的解读和分析。

首先，我们知道 Docker 是一个典型的 C/S 架构模型，我们平时使用的 `docker` 命令，是它的 CLI 客户端，而它的服务端是 dockerd ，在 Linux 系统中，通常它是由 systemd 进行管理的，我们可以通过 `systemctl status docker` 查看当前 dockerd 的运行状态。

对于构建镜像而言，它同样是需要将待构建的内容（我们称之为 context），发送给 dockerd，并由 dockerd 的特定模块最终完成构建。

### builder

这里我们需要引入一个概念 **builder** .

builder 就是上面提到的特定模块，也就是说构建内容 context 是由 Docker CLI 发送给 dockerd；并最终由 builder 完成构建。

![enter image description here](../assets/7141ec30-830d-11e9-8eb9-49b38b06f9d6.jpg)

在 `docker` 的顶级命令中，我们可以看到有一个 `builder` 的命令组。它有一个子命令 `prune` 用于清理所有构建过程中的缓存。

以下是 Docker 18.09 的输出信息。

```bash
/ # docker builder
Usage:  docker builder COMMAND
Manage builds
Commands:
  prune       Remove build cache
Run 'docker builder COMMAND --help' for more information on a command.
```

而在 Docker 19.03 中，它新增了一个子命令：

```bash
/ # docker builder
Usage:  docker builder COMMAND
Manage builds
Commands:
  build       Build an image from a Dockerfile
  prune       Remove build cache
Run 'docker builder COMMAND --help' for more information on a command.
```

这里新增的这个 `build` 子命令，其实就是我们平时使用的 `docker build` 或者是 `docker image build`，现在将它放到 builder 的子目录下也是为了凸显 builder 的概念。

builder 其实很早就存在于 Docker 当中了，我们之前在使用或者说默认在使用的就是 builder 的 v1 版本（在 Docker 内部也将它的版本号定为 1），但是由于它太久了，有一些功能缺失和不足，由此诞生了 builder 的 v2 版本，该项目被称之为 BuildKit 。

### [BuildKit](https://github.com/moby/buildkit)

BuildKit 的产生主要是由于 v1 版本的 builder 的性能，存储管理和扩展性方面都有不足（毕竟它已经产生了很久，而且近些年 Docker 火热，问题也就逐步暴露出来了）, 所以它的重点也在于解决这些问题，关键的功能列在下面：

- 支持自动化的垃圾回收
- 可扩展的构建格式
- 并发依赖解决
- 高效的缓存系统
- 插件化的架构

这些功能我们暂且略过，先回到我们的主线上来。

BuildKit 在 Docker v18.06 版本之后可通过 `export DOCKER_BUILDKIT=1` 环境变量来设置是否启用。对于 Docker v18.06 需要将 dockerd 也以实现性模式运行。即，修改 /etc/docker/daemon.json 文件，增加 `"experimental": true` 配置，然后使用 `systemctl restart docker` 重启 dockerd 。

如果将 /etc/docker/daemon.json 文件中添加以下配置：

```bash
{
  "experimental": true,
  "features": {
    "buildkit": true
  }
}
```

则会默认使用 BuildKit 进行构建，就不再需要指定环境了。

### 小结

- 在上面的内容中，我们知道了 Docker 是 C/S 架构，而我们通常使用的 `docker` 命令便是它的 CLI 客户端，服务端是 dockerd 通常由 systemd 进行管理；
- 我们介绍了一个概念 builder，它是 Docker 构建系统中的实际执行者；用于将构建的上下文 context 按照 Dockerfile 的描述最终生成 Docker 镜像（image）;
- BuildKit 是 v2 版本的 builder ；
- 我们可以通过增加 `export DOCKER_BUILDKIT=1` 的环境变量，或是修改 dockerd 的配置文件来临时启用或者默认启用 BuildKit 作为 builder。

我们来体验一下开启 BuildKit 的镜像构建：

```bash
(MoeLove) ➜  ~ docker build -t local/spring-boot:buildkit https://github.com/tao12345666333/spring-boot-hello-world.git
[+] Building 0.2s (0/1)
[+] Building 0.6s (0/1) 
...
[+] Building 6.4s (0/1)
 => [internal] load git source https://github.com/tao12345666333/spring-boot-hello-world.git                6.4s 
 => => # 已初始化空的 Git 仓库于 /var/lib/docker/overlay2/xieo69jwu3qd18uqmuwa6er9l/diff/
         898cc478c6bbec5dab019a36fdfdd2dd172cee9erefs/heads/master
[+] Building 394.0s (12/12) FINISHED
 => [internal] load git source https://github.com/tao12345666333/spring-boot-hello-world.git                6.4s 
 => [internal] load metadata for docker.io/library/openjdk:8-jre-alpine                                     3.6s
 => [internal] load metadata for docker.io/library/maven:3.6.1-jdk-8-alpine                                 3.3s 
 => CACHED [stage-2 1/2] FROM docker.io/library/openjdk:[email protected]:f362b165b870ef129cbe730f29065f  0.0s
 => => resolve docker.io/library/openjdk:[email protected]:f362b165b870ef129cbe730f29065ff37399c0aa8bcab  0.0s
 => [builder 1/6] FROM docker.io/library/maven:[email protected]:16691dc7e18e5311ee7ae38b40dcf98e  14.3s
 => => resolve docker.io/library/maven:[email protected]:16691dc7e18e5311ee7ae38b40dcf98ee1cfe4a48  0.0s
 => => sha256:e4ef40f7698347c89ee64b2e5c237d214cae777f33735c52039824eb44feb796 2.18MB / 2.18MB              2.7s
...
 => => extracting sha256:c2274a1a0e2786ee9101b08f76111f9ab8019e368dce1e325d3c284a0ca33397                   0.7s
 => [builder 2/6] WORKDIR /app                                                                              0.3s
 => [builder 3/6] COPY pom.xml /app/                                                                        0.0s
 => [builder 4/6] RUN mvn dependency:go-offline                                                           352.4s
 => [builder 5/6] COPY src /app/src                                                                         0.1s
 => [builder 6/6] RUN mvn -e -B package                                                                    16.3s
 => [stage-2 2/2] COPY --from=builder /app/target/gs-spring-boot-0.1.0.jar /                                0.1s
 => exporting to image                                                                                      0.1s
 => => exporting layers                                                                                     0.1s
 => => writing image sha256:82f3748307e8c43af8e28fc5c303b89973e22ba0d2e85c1b43648a5f0c332219                0.0s
 => => naming to docker.io/local/spring-boot:buildkit                                                       0.0s
```

以上便是一个开启了 BuildKit 的镜像构建过程，可以看到与我们之前默认的 builder 的输出之类的都不一样，这里暂不展开了，我们开始下一步的学习。

## 构建历史

我们仍然使用上次 [Chat](https://gitbook.cn/gitchat/activity/5cd527e864de19331ba79278) 中的[例子](https://github.com/tao12345666333/spring-boot-hello-world.git)：一个 Spring Boot 的项目，同样的本次 Chat 中并不涉及 Spring Boot 的任何知识。只需要知道对于这个项目而言， 需要先安装依赖、构建，才能运行。

```bash
(MoeLove) ➜  spring-boot-hello-world git:(master) ✗ ls -l 
总用量 20
-rw-rw-r--. 1 tao tao    0 5月  15 06:52 Dockerfile
drwxrwxr-x. 2 tao tao 4096 5月  15 06:54 docs
-rw-rw-r--. 1 tao tao 1992 5月  15 06:33 pom.xml
-rw-rw-r--. 1 tao tao   89 5月  15 06:50 README.md
drwxrwxr-x. 4 tao tao 4096 5月  15 06:33 src
drwxrwxr-x. 9 tao tao 4096 5月  15 06:52 target
```

我们来看下该项目的 Dockerfile 的内容：

```bash
FROM maven:3.6.1-jdk-8-alpine AS builder
WORKDIR /app
COPY pom.xml /app/
RUN mvn dependency:go-offline
COPY src /app/src
RUN mvn -e -B package
FROM builder AS dev
RUN apk add --no-cache vim
FROM openjdk:8-jre-alpine
COPY --from=builder /app/target/gs-spring-boot-0.1.0.jar /
CMD [ "java", "-jar", "/gs-spring-boot-0.1.0.jar" ]
```

我们以此 Dockerfile 来构建镜像，这里我增加了 `-q` 参数忽略掉默认的输出。

```bash
(MoeLove) ➜  spring-boot-hello-world git:(master) docker build -q -t local/spring-boot:1 .
sha256:01e4898d1141763400d39111609425ba6232b8bf42f46a6033fdb2b7306dc75b 
```

可以看到镜像已经构建成功了，这里我们来介绍一个新的命令 `docker image history`，对新构建的镜像执行此命令：

```bash
(MoeLove) ➜  spring-boot-hello-world git:(master) docker image history local/spring-boot:1
IMAGE               CREATED             CREATED BY                                      SIZE                COMMENT
01e4898d1141        292 years ago       CMD ["java" "-jar" "/gs-spring-boot-0.1.0.ja…   0B                  buildkit.dockerfile.v0
<missing>           2 days ago          COPY /app/target/gs-spring-boot-0.1.0.jar / …   18.2MB              buildkit.dockerfile.v0
<missing>           2 weeks ago         /bin/sh -c set -x  && apk add --no-cache   o…   79.4MB              
<missing>           2 weeks ago         /bin/sh -c #(nop)  ENV JAVA_ALPINE_VERSION=8…   0B                  
<missing>           2 weeks ago         /bin/sh -c #(nop)  ENV JAVA_VERSION=8u212       0B                  
<missing>           2 weeks ago         /bin/sh -c #(nop)  ENV PATH=/usr/local/sbin:…   0B                  
<missing>           2 weeks ago         /bin/sh -c #(nop)  ENV JAVA_HOME=/usr/lib/jv…   0B                  
<missing>           2 weeks ago         /bin/sh -c {   echo '#!/bin/sh';   echo 'set…   87B
<missing>           2 weeks ago         /bin/sh -c #(nop)  ENV LANG=C.UTF-8             0B                  
<missing>           2 weeks ago         /bin/sh -c #(nop)  CMD ["/bin/sh"]              0B                  
<missing>           2 weeks ago         /bin/sh -c #(nop) ADD file:a86aea1f3a7d68f6a…   5.53MB
```

可以看到我们镜像的构建记录（以逆序排列），最上面的部分是我们多阶段构建中的。

```bash
COPY --from=builder /app/target/gs-spring-boot-0.1.0.jar /
CMD [ "java", "-jar", "/gs-spring-boot-0.1.0.jar" ]
```

这两步所对应的内容。

而下面的部分，则是我们的基础镜像 `openjdk:8-jre-alpine` 的构建记录。我们的操作基本都可以在 history 中看到。

### 构建历史的不安全性

假如，我们的项目在构建过程当中，需要连接远端的数据库获取对应的信息（比如：获取某个特定的配置），之后才可以进行构建，我们通常情况下会如何去做呢？

- 将密码硬编码写入代码中，如果使用此方法，当密码变更的时候，便需要修改代码才能支持，并且镜像分发的时候，会造成信息泄漏，导致安全问题；
- 通过环境变量的方式构建，相对灵活，比较容易满足需求。

这里我们对 Dockerfile 做一点小改变，比如：我们使用 ENV 将密码通过环境变量的方式注入到镜像中。

```bash
# 以下省略了基础镜像的构建记录
(MoeLove) ➜  spring-boot-hello-world git:(master) ✗ docker build -q -t local/spring-boot:2 .                    
sha256:2f85141a35c386bbeac0ba77acd470025682bebc7da9eb204295ff8fafb6e0a8                                         
(MoeLove) ➜  spring-boot-hello-world git:(master) ✗ docker image history local/spring-boot:2                    
IMAGE               CREATED             CREATED BY                                      SIZE                COMMENT
2f85141a35c3        292 years ago       CMD ["java" "-jar" "/gs-spring-boot-0.1.0.ja…   0B                  buildkit.dockerfile.v0
<missing>           292 years ago       ENV CACHE_PASSWD=moelove                        0B                  buildkit.dockerfile.v0
<missing>           2 days ago          COPY /app/target/gs-spring-boot-0.1.0.jar / …   18.2MB              buildkit.dockerfile.v0
<missing>           2 weeks ago         /bin/sh -c set -x  && apk add --no-cache   o…   79.4MB 
...
```

很明显，刚才增加的 ENV 可以直接通过 docker history/docker image history 看到。 **不建议真的这样做** 。

由此，得出了我们的第一个结论， **Docker 镜像的构建历史是不安全的，通过 ENV 设置的信息可在 history 中看到** 。

这也引出了我们的第一个问题： **Docker 镜像的构建记录是可查看的，如何管理构建过程中需要的密码/密钥等敏感信息？** ### 高阶特性：密码管理

为了应对类似前面这样的问题，当开启 BuildKit 时，我们可以使用高阶用法，即：Dockerfile 的实验特性。

Dockerfile 的实验特性，通过给它的顶部添加 `# syntax = docker/dockerfile:experimental` 来实现，这也是 BuildKit 扩展性的一种表现形式。

具体用法如下：

```bash
# syntax = docker/dockerfile:experimental
COPY fetch_remote_data.sh .
RUN --mount=type=secret,id=moelove,target=/cache_builder,required ./fetch_remote_data.sh
```

然后通过以下命令进行构建:

```bash
docker build --secret id=moelove,src=./secret -t local/spring-boot:4 .
```

构建成功后，我们来看下 history 的记录：

```bash
(MoeLove) ➜  spring-boot-hello-world git:(master) ✗ docker history local/spring-boot:4        
IMAGE               CREATED             CREATED BY                                      SIZE                COMMENT
b5fcff644568        292 years ago       CMD ["java" "-jar" "/gs-spring-boot-0.1.0.ja…   0B                  buildkit.dockerfile.v0
<missing>           2 minutes ago       RUN /bin/sh -c ./fetch_remote_data.sh # buil…   19B                 buildkit.dockerfile.v0
<missing>           2 minutes ago       COPY fetch_remote_data.sh . # buildkit          37B                 buildkit.dockerfile.v0
<missing>           2 days ago          COPY /app/target/gs-spring-boot-0.1.0.jar / …   18.2MB              buildkit.dockerfile.v0
...
```

并没有在记录中看到我们的密码，同时，当我们用该镜像启动一个容器后会发现，刚才挂载进去的文件变成空的了。

### 高阶特性：密钥管理

另一种很常见的情况是，在构建过程中，可能需要 `git clone` 一个私有仓库，或者是 `ssh` 到某个远程主机上获取一些数据之类的操作。

对于这种情况，我们也可以使用高阶特性, （这里就不在上面例子的基础上来写了，写了一个新的 Dockerfile）。

```bash
# syntax = docker/dockerfile:experimental
FROM alpine
# 安装必要的包
RUN apk add --no-cache git openssh-client
# 创建必要的目录 .ssh 由于要使用 ssh 连接，所以需要使用 ssh-keyscan 先获取 public SSH host key
# 当然也可以给 .ssh/config 写配置文件来跳过验证，但容易带来安全问题，不推荐
RUN mkdir -p -m 0700 ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts
# clone 私有项目仓库，并创建分支
RUN --mount=type=ssh,required git clone [email protected]:tao12345666333/moe.git \
        && cd moe \
        && git checkout -b release
```

**注意** ：使用此功能的时候，需要使用 [`ssh-agent(1)`](https://linux.die.net/man/1/ssh-agent) 进行认证代理，所以需要提前安装。

构建方式如下：

```bash
(MoeLove) ➜  d eval $(ssh-agent)
Agent pid 28184
(MoeLove) ➜  d ssh-add ~/.ssh/id_rsa
Enter passphrase for /home/tao/.ssh/id_rsa:
Identity added: /home/tao/.ssh/id_rsa (/home/tao/.ssh/id_rsa)
(MoeLove) ➜  d docker build --ssh=default -t local/ssh .
\[+\] Building 0.5s (10/10) FINISHED
=> \[internal\] load build definition from Dockerfile                                                 0.1s
=> => transferring dockerfile: 96B                                                                  0.0s
=> \[internal\] load .dockerignore                                                                    0.1s
=> => transferring context: 2B                                                                      0.0s
=> resolve image config for docker.io/docker/dockerfile:experimental                                0.0s
=> CACHED docker-image://docker.io/docker/dockerfile:experimental                                   0.0s
=> \[internal\] load metadata for docker.io/library/alpine:latest                                     0.0s
=> \[1/4\] FROM docker.io/library/alpine                                                              0.0s
=> CACHED \[2/4\] RUN apk add --no-cache git openssh-client                                           0.0s
=> CACHED \[3/4\] RUN mkdir -p -m 0700 ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts         0.0s
=> CACHED \[4/4\] RUN --mount=type=ssh,required git clone \[email protected\]:tao12345666333/moe.git       0.0s
=> exporting to image                                                                               0.0s
=> => exporting layers                                                                              0.0s
=> => writing image sha256:35d3ded5595a48de50054121feed13ebadf9b5e73b6cefeeba4215e1a20a20fd         0.0s
=> => naming to docker.io/local/ssh
```

我们使用该镜像启动一个容器：

```bash
(MoeLove) ➜  d docker run --rm -it local/ssh
/ # du -sh moe/
108.0K  moe/
/ # ls -al ~/.ssh/\*
-rw-r--r--    1 root     root           788 May 30 06:35 /root/.ssh/known_hosts
```

可以看到，代码仓库已经成功的 clone 下来了。同时，在 `~/.ssh` 目录内也并没有保留任何我们公/私钥的信息。

```bash
(MoeLove) ➜  d docker history local/ssh
IMAGE               CREATED             CREATED BY                                      SIZE                COMMENT
35d3ded5595a        35 minutes ago      RUN /bin/sh -c git clone \[email protected\]:tao1…   16.9kB              buildkit.dockerfile.v0
<missing>           35 minutes ago      RUN /bin/sh -c mkdir -p -m 0700 ~/.ssh && ss…   392B                buildkit.dockerfile.v0
<missing>           36 minutes ago      RUN /bin/sh -c apk add --no-cache git openss…   20.8MB              buildkit.dockerfile.v0
<missing>           2 weeks ago         /bin/sh -c #(nop)  CMD \["/bin/sh"\]              0B
<missing>           2 weeks ago         /bin/sh -c #(nop) ADD file:a86aea1f3a7d68f6a…   5.53MB
```

镜像的 history 中也没有任何额外的敏感信息。

如果没有运行 `ssh-agent` 或者是密钥没有 ssh-add 添加进去， 你就会看到类似下面的问题：

```bash
## (MoeLove) ➜  d docker build --no-cache --ssh=default -t local/ssh . \[+\] Building 11.9s (9/9) FINISHED => \[internal\] load .dockerignore                                                                    0.1s => => transferring context: 2B                                                                      0.0s => \[internal\] load build definition from Dockerfile                                                 0.1s => => transferring dockerfile: 96B                                                                  0.0s => resolve image config for docker.io/docker/dockerfile:experimental                                0.0s => CACHED docker-image://docker.io/docker/dockerfile:experimental                                   0.0s => \[internal\] load metadata for docker.io/library/alpine:latest                                     0.0s => CACHED \[1/4\] FROM docker.io/library/alpine                                                       0.0s => \[2/4\] RUN apk add --no-cache git openssh-client                                                  5.5s => \[3/4\] RUN mkdir -p -m 0700 ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts                3.0s => ERROR \[4/4\] RUN --mount=type=ssh,required git clone \[email protected\]:tao12345666333/moe.git        2.9s

> \[4/4\] RUN --mount=type=ssh,required git clone \[email protected\]:tao12345666333/moe.git         && cd moe         && git checkout -b release:

# 9 0.691 Cloning into 'moe'

# 9 1.923 Warning: Permanently added the RSA host key for IP address '192.30.253.112' to the list of known hosts

# 9 2.842 \[email protected\]: Permission denied (publickey)

# 9 2.843 fatal: Could not read from remote repository

# 9 2.843

# 9 2.843 Please make sure you have the correct access rights

# 9 2.843 and the repository exists

______________________________________________________________________

rpc error: code = Unknown desc = executor failed running \[/bin/sh -c git clone \[email protected\]:tao12345666333/moe.git         && cd moe         && git checkout -b release\]: exit code: 128
```

### 小结

在上面的内容中，我们学习到了通过 `docker image history` 可以查看镜像的构建历史，但构建历史是透明的，凡是可以拿到该镜像的人均可查看到其构建历史；所以它是不安全的。

尤其是当我们通过 ENV 或者 RUN 指令等，将密码/配置信息等传递进去，或者是将自己的私钥之类的文件拷贝到镜像中， **这些操作都是不安全的，不应该这样使用** ，在启用 BuildKit 之后，我们可以通过使用新的实验性语法做到更安全的操作。

实验性语法是在 Dockerfile 的头部增加了一个表示当前语法规则的 `# syntax = docker/dockerfile:experimental` （事实上，我们将它称之为 frontend）它其实是一个真实存在的 Docker 镜像，在构建过程中，会将它拉取下来使用，这里的详细内容我们可以之后对 frontend 详解的时候再进行讨论。

在 Dockerfile 中通过使用 `RUN --mount=type=ssh` 或是 `RUN --mount=type=secret` 的方式，配合 `docker build` 时，传递 `--ssh` 或 `--secret` 参数即可使用。可参考[官方文档](https://docs.docker.com/develop/develop-images/build_enhancements/)了解更多。

这是一种 **推荐** 且 **安全** 的处理方式，虽然就结果而言这并不是唯一的解决方案，但我还是推荐你及时升级 `Docker` 并使用这种方式。

## Docker 19.03 构建系统解读

Docker 19.03 在（2019/05/30 发布了 beta5 版本）正式版也将在不久之后会发布。相比其他版本而言，19.03 在构建系统方面的变化是比较大的，虽然一些特性是 18.09 时就已经增加的。

### builder cache 管理

在 18.09 之前，有一个命令 `docker system prune` 可以清除所有的停止状态的容器、所有未被使用的网络、所有 dangling 状态的镜像以及所有 dangling 状态的构建缓存。

但有时候你可能并不想把他们都删掉。在 18.09 版本中，新增了 `docker builder prune` 命令，该命令可以只删除所有的 BuildKit 的构建缓存。

同样的，之前 builder 产生的构建缓存是需要手动进行清理的，否则磁盘空间将会浪费很多。在 18.09 之后也为 BuildKit 增加了可配置的垃圾回收策略。

具体配置方式是（Docker 19.03 中）在 /etc/docker/daemon.json 中写入以下内容：

```bash
{
"experimental": true,
"features": {
"buildkit": true
},
"builder": {
    "gc": {
      "enabled": true,
      "defaultKeepStorage": "20GB"
    }
  }
}
```

以上配置中 experimental 表示是否开启实验性功能，features 中是选择开启 BuildKit 支持，builder 中的 gc 则表示控制垃圾回收的策略，上面配置的含义是：保留 20G 的缓存，超出则会进行清理。

### 多实例 builder 管理

我们知道 Docker CLI 是提供插件支持的，并且开发一个插件也并不难，不过这不是今天的重点，之后开 Chat 再聊。

Docker 19.03 会提供两个主要的插件 app 和 buildx；buildx 就是这一小节的主角。

如果你安装了 Docker 19.03 但你输入 `docker buildx` 发现报错时，那说明你的 Docker 还尚未安装 buildx，可以使用下面的命令进行安装：

```bash
(MoeLove) ➜  export DOCKER_BUILDKIT=1
(MoeLove) ➜  docker build --platform=local -o . git://github.com/docker/buildx
(MoeLove) ➜  mkdir -p ~/.docker/cli-plugins/
(MoeLove) ➜  mv buildx ~/.docker/cli-plugins/docker-buildx
```

完成后，执行 `docker buildx` 就会看到以下内容的输出：

```bash
(MoeLove) ➜  ~ docker buildx
Usage:  docker buildx COMMAND
Build with BuildKit
Management Commands:
imagetools  Commands to work on images in registry
Commands:
bake        Build from a file
build       Start a build
create      Create a new builder instance
inspect     Inspect current builder instance
ls          List builder instances
rm          Remove a builder instance
stop        Stop builder instance
use         Set the current builder instance
version     Show buildx version information
Run 'docker buildx COMMAND --help' for more information on a command.
```

buildx 主要作用其实是为了扩展 BuildKit 的能力，包括多 builder 实例的管理；多 node 构建以支持扩平台构建等能力。

我们主要来看下如何使用它，深入的分析之后再进行讨论。

我们来演示多实例构建。首先需要创建一个 builder 实例。

```bash
(MoeLove) ➜  docker buildx create --name d1809 172.17.0.3
d1809
(MoeLove) ➜  docker buildx ls
NAME/NODE DRIVER/ENDPOINT       STATUS   PLATFORMS
d1809     docker-container
d18090  tcp://172.17.0.3:2375 inactive
d1903 *   docker-container
d19030  tcp://172.17.0.2:2375 running  linux/amd64
default   docker
default default               running  linux/amd64
```

`docker buildx create` 通过 `--name` 来指定 builder 的名称，最后跟的是 host/IP 地址，默认使用 2375 端口。

如果要使用新创建的 builder 需要先通过 `docker buildx use` 命令来进行切换，当前在使用的 builder 通过 `ls` 命令的时候会带有一个 `*` 标记。当然你也可能注意到了它当前的状态是 inactive，这是因为只有当它真正开始构建任务了或者是执行过构建任务了 agent 才会启动，将它注册回来。

```bash
(MoeLove) ➜  ~ docker buildx use d1809
(MoeLove) ➜  ~ docker buildx ls
NAME/NODE DRIVER/ENDPOINT       STATUS   PLATFORMS
d1809 *   docker-container
d18090  tcp://172.17.0.3:2375 inactive
d1903     docker-container
d19030  tcp://172.17.0.2:2375 running  linux/amd64
default   docker
default default               running  linux/amd64
```

接下来还是以前面的 Spring Boot 的项目为例进行构建：

```bash
(MoeLove) ➜  spring-boot-hello-world git:(master) docker buildx build --load -t remote/spring-boot:1 .
\[+\] Building 31.1s (6/14)
\[+\] Building 686.6s (16/16) FINISHED
=> \[internal\] booting buildkit                                                                            21.2s
=> => pulling image moby/buildkit:master                                                                  20.7s
=> => creating container buildx_buildkit_d18090                                                            0.5s
=> => unpacking docker.io/library/openjdk:\[email protected\]:f362b165b870ef129cbe730f29065ff37399c0aa8bc  2.2s
=> \[builder 2/6\] WORKDIR /app                                                                              0.0s
=> \[builder 3/6\] COPY pom.xml /app/                                                                        0.1s
=> \[builder 4/6\] RUN mvn dependency:go-offline                                                           596.4s
=> \[builder 5/6\] COPY src /app/src                                                                         0.2s
=> \[builder 6/6\] RUN mvn -e -B package                                                                    25.3s
=> \[stage-2 2/2\] COPY --from=builder /app/target/gs-spring-boot-0.1.0.jar /                                0.2s
=> exporting to oci image format                                                                           2.3s
=> => exporting layers                                                                                     1.3s
=> => exporting manifest sha256:f5af6ad923434c4d7d2d6f94f095ccacfe6983cec592de6b8a0a3af37206686a           0.0s
=> => exporting config sha256:644867602b8a4a5162dee8534378e3dab28807f593759c6b25bcf16492d807bc             0.0s
=> => sending tarball                                                                                      0.9s
=> importing to docker                                                                                     0.3s
(MoeLove) ➜  spring-boot-hello-world git:(master) docker image ls remote/spring-boot
REPOSITORY           TAG                 IMAGE ID            CREATED              SIZE
remote/spring-boot   1                   644867602b8a        About a minute ago   103MB
```

镜像构建成功了。 **注意** 这里给 `docker buildx build` 命令传递了 `--load` 参数，表示我们要将构建好的镜像加载到我们现在在用的 dockerd 当中。

此时再查看 builder 的状态：

```bash
(MoeLove) ➜  spring-boot-hello-world git:(master) docker buildx ls
NAME/NODE DRIVER/ENDPOINT       STATUS  PLATFORMS
d1809 *   docker-container
d18090  tcp://172.17.0.3:2375 running linux/amd64
d1903     docker-container
d19030  tcp://172.17.0.2:2375 running linux/amd64
default   docker
default default               running linux/amd64
```

可以看到它状态已经上报回来了，处于了 running 状态了。

我们到这个 builder 实际对应的机器上查看该机器上容器的状态：

```bash
/ # docker ps
CONTAINER ID        IMAGE                  COMMAND             CREATED             STATUS              PORTS               NAMES
ff4a9e18658e        moby/buildkit:master   "buildkitd"         About an hour ago   Up About an hour                        buildx_buildkit_d18090
```

可以看到实际上是在该机器的 Docker 中运行了一个 BuildKit 的后端容器，以此来进行构建相关的操作。

当然，buildx 还有很多特性，比如可以构建多架构平台的镜像等。可以通过[官方文档](https://github.com/docker/buildx/blob/master/README.md.html)对它进一步了解。

### 小结

通过这一小节，我们了解到在 Docker 19.03 版本中，我们可以通过 `docker builder prune` 清理构建缓存；并且可以通过给 /etc/docker/daemon.json 中写配置的方式来开启构建缓存的自动垃圾回收机制，以减轻磁盘压力。

buildx 是 Docker 的一个 CLI 插件，默认安装完 19.03 后将会同时安装它，当然你也可以手动进行安装。我们通过 buildx 可以进行多个 builder 实例的管理，通过这种方式，可以将很多机器组成一个集群来分担构建压力，或者是分担不同架构的构建任务等。

## 发现并优化镜像大小 dive

镜像的构建系统我们了解的差不多了，我们再聊聊如何发现，并优化镜像大小。这里分两个部分，其一是，发现；其二是，优化。

### 发现

首先推荐一个工具 [dive](https://github.com/wagoodman/dive) ; 通过上次的 Chat 我们已经知道了镜像的组成和结构，dive 是一个命令行工具，使用它可以浏览 Docker 镜像每层的内容，以此来发现我们镜像中是否有什么不需要的东西存在。

关于 dive 这里不做过多介绍了，该项目的文档中介绍还是比较详细的，我们可以用它来分析下刚才我们构建成功的镜像：

![enter image description here](../assets/2f5601d0-830d-11e9-a8d7-c164a8393e9a.jpg)

第二种方法，则是比较一般的，通过之前介绍的 `docker image history` 来查看构建记录和每层的大小，以此来观察是否有非必要的操作之类的。

### 优化

我们对前面所举例中的 Spring Boot 项目的 Dockerfile 做点小改动：

```bash
FROM maven:3.6.1-jdk-8-alpine AS builder
WORKDIR /app
COPY pom.xml /app/
RUN mvn dependency:go-offline
COPY src /app/src
RUN mvn -e -B package
FROM builder AS dev
RUN apk add --no-cache vim
FROM openjdk:8-jre-alpine
COPY --from=builder /app/target/gs-spring-boot-0.1.0.jar /

# 增加两句完全没必要的操作，仅做演示

COPY --from=builder /app/target/gs-spring-boot-0.1.0.jar /tmp/
RUN rm /tmp/gs-spring-boot-0.1.0.jar
CMD \[ "java", "-jar", "/gs-spring-boot-0.1.0.jar" \]
```

给它增加了两句完全没有必要的操作，现在构建该镜像。

```bash
(MoeLove) ➜  spring-boot-hello-world git:(master) ✗ docker image ls remote/spring-boot\
REPOSITORY           TAG                 IMAGE ID            CREATED             SIZE
remote/spring-boot   2                   11559170c3fd        7 minutes ago       121MB
remote/spring-boot   1                   644867602b8a        About an hour ago   103MB
```

可以看到使用上面修改后的 Dockerfile 构建的镜像比之前的镜像大了 18M；我们之前也讲过了，镜像是层的叠加，后面操作删掉的文件，并不会减少镜像的体积。

**那我们如何在不修改 Dockerfile 的情况下让镜像体积变小呢？答案就在构建系统上。** 我们可以通过给 `docker build` 传递 `--squash` 的参数，来将镜像的层进行合并。

```bash
(MoeLove) ➜  spring-boot-hello-world git:(master) ✗ docker build --squash -t remote/spring-boot:3 .
\[+\] Building 2.5s (16/16) FINISHED
...
=> exporting to image                                                                                      0.0s
=> => exporting layers                                                                                     0.0s
=> => writing image sha256:2d5ba7eb86d2ad5594f82a896637c91137d150dab61fe8dc3acbdfcd164f6686                0.0s
=> => naming to docker.io/remote/spring-boot:3                                                             0.0s
```

查看构建好的镜像大小：

```bash
(MoeLove) ➜  spring-boot-hello-world git:(master) ✗ docker image ls remote/spring-boot
REPOSITORY           TAG                 IMAGE ID            CREATED             SIZE
remote/spring-boot   3                   a2c1e139697b        5 seconds ago       103MB
remote/spring-boot   2                   11559170c3fd        12 minutes ago      121MB
remote/spring-boot   1                   644867602b8a        About an hour ago   103MB
```

可以看到镜像的体积又恢复了正常，这表示我们对之前层的删除操作生效了。我们来看看构建历史：

```bash
(MoeLove) ➜  spring-boot-hello-world git:(master) ✗ docker image history remote/spring-boot:3
IMAGE               CREATED              CREATED BY                                      SIZE                COMMENT
a2c1e139697b        About a minute ago                                                   103MB               create new from sha256:2d5ba7eb86d2ad5594f82a896637c91137d150dab61fe8dc3acbdfcd164f6686
<missing>           292 years ago        CMD \["java" "-jar" "/gs-spring-boot-0.1.0.ja…   0B                  buildkit.dockerfile.v0
<missing>           About a minute ago   RUN /bin/sh -c rm /tmp/gs-spring-boot-0.1.0.…   0B                  buildkit.dockerfile.v0
<missing>           About a minute ago   COPY /app/target/gs-spring-boot-0.1.0.jar /t…   0B                  buildkit.dockerfile.v0
<missing>           3 days ago           COPY /app/target/gs-spring-boot-0.1.0.jar / …   0B                  buildkit.dockerfile.v0
<missing>           2 weeks ago          /bin/sh -c set -x  && apk add --no-cache   o…   0B
<missing>           2 weeks ago          /bin/sh -c #(nop)  ENV JAVA_ALPINE_VERSION=8…   0B
<missing>           2 weeks ago          /bin/sh -c #(nop)  ENV JAVA_VERSION=8u212       0B
<missing>           2 weeks ago          /bin/sh -c #(nop)  ENV PATH=/usr/local/sbin:…   0B
<missing>           2 weeks ago          /bin/sh -c #(nop)  ENV JAVA_HOME=/usr/lib/jv…   0B
<missing>           2 weeks ago          /bin/sh -c {   echo '#!/bin/sh';   echo 'set…   0B
<missing>           2 weeks ago          /bin/sh -c #(nop)  ENV LANG=C.UTF-8             0B
<missing>           2 weeks ago          /bin/sh -c #(nop)  CMD \["/bin/sh"\]              0B
<missing>           2 weeks ago          /bin/sh -c #(nop) ADD file:a86aea1f3a7d68f6a…   0B
```

可以看到之前的每层大小都已经变成了 0，这是因为把所有的层都合并到了最终的镜像上去了。 **特别注意：** `--squash` 虽然在 1.13.0 版本中就已经加入了 Docker 中，但他至今仍然是实验形式；所以你需要按照我在本篇文章开始部分的介绍那样，打开实验性功能的支持。

但直接传递 `--squash` 的方式，相对来说足够的简单，也更安全。

## 总结

通过本次 Chat 我们学习到了关于 Docker builder 的概念，以及了解到了下一代版本的 BuildKit；学习了 Docker 19.03 中多实例的构建，以及对构建缓存的垃圾回收配置等；学习了 Dockerfile 的高阶特性，并通过这些特性来管理密码和密钥等信息；学习了如何发现并优化镜像的体积。

以上内容中虽然没有具体到它们的全部功能，也没有深入到源码级的分析，但已经涵盖了 Docker 构建系统的最新特性，希望能对你有所帮助。
