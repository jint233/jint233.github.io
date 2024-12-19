# 高效构建 Docker 镜像的最佳实践

在真正实践之前，我们需要先搞明白几个问题：

- Docker 镜像是什么
- Docker 镜像的作用
- 容器和镜像的区别及联系

## Docker 镜像是什么

这里，我们以一个 Debian 系统的镜像为例。通过 `docker run --it debian` 可以启动一个 `debian` 的容器，终端会有如下输出：

```bash
/ # docker run -it debian
Unable to find image 'debian:latest' locally
latest: Pulling from library/debian
c5e155d5a1d1: Pull complete 
Digest: sha256:75f7d0590b45561bfa443abad0b3e0f86e2811b1fc176f786cd30eb078d1846f
Status: Downloaded newer image for debian:latest
[email protected]:/# cat /etc/os-release 
PRETTY_NAME="Debian GNU/Linux 9 (stretch)"
NAME="Debian GNU/Linux"
VERSION_ID="9"
VERSION="9 (stretch)"
ID=debian
HOME_URL="https://www.debian.org/"
SUPPORT_URL="https://www.debian.org/support"
BUG_REPORT_URL="https://bugs.debian.org/"
[email protected]:/# 
```

看终端的日志，首先会查找本地是否有 `debian` 的镜像，如果没有则从镜像仓库（若不指定，默认是 docker.io）pull；pull 镜像成功后，再以此镜像来启动容器。

我们可以先退出此容器，来看看 Docker 镜像到底是什么。用 `docker image ls` 来查看已下载好的镜像：

```bash
/ # docker image ls
REPOSITORY          TAG                 IMAGE ID            CREATED             SIZE
debian              latest              8d31923452f8        4 days ago          101MB
```

用 `docker image save` 命令将镜像保存成一个 tar 文件：

```bash
/ # mkdir debian-image
/ # docker image save -o debian-image/debian.tar debian
/ # ls debian-image/
debian.tar
```

将镜像文件进行解压：

```bash
/ # tar -C debian-image/ -xf debian-image/debian.tar 
/ # tree -I debian.tar debian-image/
debian-image/
├── 8d31923452f8b79ae91b01568d28c90e7d667a9eaff9734c6faeb017b0efa8d0.json
├── b50334e3be68f82d0b94bb7d3cfe1789119c040c6c159759f57a19ad34547af3
│   ├── VERSION
│   ├── json
│   └── layer.tar
├── manifest.json
└── repositories
1 directory, 6 files
```

可以看到将镜像文件解压后，包含的内容主要是一些配置文件和 tar 包。

接下来我们来具体看看其中的内容，并通过这些内容来理解镜像的组成。

## manifest.json

```json
/debian-image # cat manifest.json  | jq
[
  {
    "Config": "8d31923452f8b79ae91b01568d28c90e7d667a9eaff9734c6faeb017b0efa8d0.json",
    "RepoTags": [
      "debian:latest"
    ],
    "Layers": [
      "b50334e3be68f82d0b94bb7d3cfe1789119c040c6c159759f57a19ad34547af3/layer.tar"
    ]
  }
]
```

**注意：在实际存储时，是不包含空格的，这里为了便于展示所以使用了 jq 工具进行格式化。**

`manifest.json` 包含了镜像的顶层配置，它是一系列配置按顺序组织而成的；以现在我们的 `debian` 镜像为例，它至包含了一组配置，这组配置中包含了 3 个主要的信息，我们由简到繁进行说明。

## RepoTags

`RepoTags` 表示镜像的名称和 tag ，这里简要的对此进行说明：`RepoTags` 其实分为两部分：

- `Repo`: Docker 镜像可以存储在本地或者远端镜像仓库内，Repo 其实就是镜像的名称。 Docker 默认提供了大量的官方镜像存储在 [Docker Hub](https://hub.docker.com/u/library) 上，对于我们现在在用的这个 Docker 官方的 debian 镜像而言，完整的存储形式其实是 `docker.io/library/debian`，只不过 docker 自动帮我们省略掉了前缀。
- `Tag`: 我们可以通过 `repo:tag` 的方式来引用一个镜像，默认情况下，如果没有指定 tag （像我们上面操作的那样），则会 pull 下来最新的镜像（即：latest）

## Config

`Config` 字段包含的内容是镜像的全局配置。我们来看看具体内容：

```bash
/debian-image # cat 8d31923452f8b79ae91b01568d28c90e7d667a9eaff9734c6faeb017b0efa8d0.json  | jq
{
  "architecture": "amd64",
  "config": {                                                                     
    "Hostname": "",    
    "Domainname": "",          
    "User": "",
    "AttachStdin": false,
    "AttachStdout": false,
    "AttachStderr": false,
    "Tty": false,
    "OpenStdin": false,
    "StdinOnce": false,
    "Env": [
      "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    ],
    "Cmd": [
      "bash"
    ],
    "ArgsEscaped": true,
    "Image": "sha256:913ee5b96cb28ad1d43f11df4aeceee963fa07b53edccb3052a21939cae4a041",
    "Volumes": null,
    "WorkingDir": "",
    "Entrypoint": null,
    "OnBuild": null,
    "Labels": null
  },
  "container": "e896ef8effcc3a696087509347ad072bf1ccfbd88e2e9e7a59d20293196bafa3",
  "container_config": {
    "Hostname": "e896ef8effcc",
    "Domainname": "",
    "User": "",
    "AttachStdin": false,
    "AttachStdout": false,
    "AttachStderr": false,
    "Tty": false,
    "OpenStdin": false,
    "StdinOnce": false,
    "Env": [
      "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    ],
    "Cmd": [
      "/bin/sh",
      "-c",
      "#(nop) ",
      "CMD [\"bash\"]"
    ],
    "ArgsEscaped": true,
    "Image": "sha256:913ee5b96cb28ad1d43f11df4aeceee963fa07b53edccb3052a21939cae4a041",
    "Volumes": null,
    "WorkingDir": "",
    "Entrypoint": null,
    "OnBuild": null,
    "Labels": {}
  },
  "created": "2019-05-08T00:33:10.318602909Z",
  "docker_version": "18.06.1-ce",
  "history": [
    {
      "created": "2019-05-08T00:33:09.837482517Z",
      "created_by": "/bin/sh -c #(nop) ADD file:caf91edab64f988bc24766c58ee66c00311c7c921296b8e5b51d7023422a1485 in / "
    },
    {
      "created": "2019-05-08T00:33:10.318602909Z",
      "created_by": "/bin/sh -c #(nop)  CMD [\"bash\"]",
      "empty_layer": true
    }
  ],
  "os": "linux",
  "rootfs": {
    "type": "layers",
    "diff_ids": [
      "sha256:f94641f1fe1f5c42c325652bf55f0513c881c86b620b912b15460e0bca07cc12"
    ]
  }
}
```

以上是配置文件的全部内容。其含义如下：

- `architecture` 和 `os` : 表示架构及系统不再展开；
- `docker_version` : 构建镜像时所用 docker 的版本；
- `created`：镜像构建完成的时间；
- `history`: 镜像构建的历史记录，后面内容中再详细介绍；
- `rootfs`: 镜像的根文件系统;

重点介绍下 `rootfs`：我们知道 `rootfs` 其实是指 `/` 下一系列文件目录的组织结构；虽然 Docker 容器与我们的主机（或者称之为宿主机）共享同一个 Linux 内核，但它也有自己完整的 `rootfs`; 我们继续回到一开始的实验环境中即我们刚才创建的这个容器内看看 `/` 下有什么：

```bash
/# tree -L 1 /
/
|-- bin
|-- boot
|-- dev
|-- etc
|-- home
|-- lib
|-- lib64
|-- media
|-- mnt
|-- opt
|-- proc
|-- root
|-- run
|-- sbin
|-- srv
|-- sys
|-- tmp
|-- usr
`-- var
19 directories, 0 files
```

可以看到与我们正常 Linux 系统的 `/` 下目录相同。

回到这个例子当中，我们来看看这段配置的具体含义。由于一开始在 `manifest.json` 中已经定义了 layer 的内容，我们来看看该 layer 的 `sha256sum` 值：

```bash
/debian-image # ls b50334e3be68f82d0b94bb7d3cfe1789119c040c6c159759f57a19ad34547af3/
VERSION    json       layer.tar
/debian-image # 
/debian-image # sha256sum b50334e3be68f82d0b94bb7d3cfe1789119c040c6c159759f57a19ad34547af3/layer.tar 
f94641f1fe1f5c42c325652bf55f0513c881c86b620b912b15460e0bca07cc12  b50334e3be68f82d0b94bb7d3cfe1789119c040c6c159759f57a19ad34547af3/layer.tar
```

可以看到与配置文件中相符，表示 `b50334e3be68f82d0b94bb7d3cfe1789119c040c6c159759f57a19ad34547af3/layer.tar` 便是 debian 镜像的 `rootfs` 我们将它进行解压，看看它的内容。

```bash
/debian-image # mkdir b50334e3be68f82d0b94bb7d3cfe1789119c040c6c159759f57a19ad34547af3/layer
/debian-image # tar -C b50334e3be68f82d0b94bb7d3cfe1789119c040c6c159759f57a19ad34547af3/layer -xf b50334e3be68f82
d0b94bb7d3cfe1789119c040c6c159759f57a19ad34547af3/layer.tar 
/debian-image # ls b50334e3be68f82d0b94bb7d3cfe1789119c040c6c159759f57a19ad34547af3/layer
bin    dev    home   lib64  mnt    proc   run    srv    tmp    var
boot   etc    lib    media  opt    root   sbin   sys    usr
```

可以看到它的内容确实是 `rootfs` 应该有的内容。同时，上面操作中也包含了一个知识点：

- **Docker 镜像相关的配置中，所用的 id 或者文件名/目录名大多是采用 sha256sum 计算得出的**

关于配置的部分我们先谈这些，我们继续看配置中尚未解释的 `Layers`。

## Layers

其实根据前面的介绍，我们已经大致看到，Docker 镜像是分层的模式，将一系列层按顺序组织起来加上配置文件等共同构成完整的镜像。这样做的好处主要有：

- 相同内容可以复用, 减轻存储负担；
- 可以比较容易的得到各层所做操作/操作后结果的记录；
- 后续操作不影响前一层的内容。

通过 `manifest.json` 的内容，和前面对 `rootfs` 的解释，不难看出此镜像只包含了一层，即 `b50334e3be68f82d0b94bb7d3cfe1789119c040c6c159759f57a19ad34547af3/layer.tar` 。

Docker 提供了一个命令可以更加直观的看到构建记录：

```bash
/debian-image # docker image history  debian
IMAGE               CREATED             CREATED BY                                      SIZE                COMMENT
8d31923452f8        4 days ago          /bin/sh -c #(nop)  CMD ["bash"]                 0B                      
<missing>           4 days ago          /bin/sh -c #(nop) ADD file:caf91edab64f988bc…   101MB                   
```

它的输出相比我们上面配置文件中的内容，多了一列 `SIZE`，表示该构建步骤所占空间大小。可以看到第二步(输出是逆序的) `/bin/sh -c #(nop) CMD ["bash"]` 所占空间为 0 。

我们首先分解这些步骤所表示的内容：

- `/bin/sh -c #(nop) ADD file:caf91edab64f988bc…`: 使用 `ADD` 命令添加文件；
- `/bin/sh -c #(nop) CMD ["bash"]`：使用 `CMD` 配置默认执行的程序是 `bash` 。

从前面 `Config` 的配置中，我们也可以看到第二步其实是修改了 `Config` 的配置，所以占用空间为 0，并没有使镜像变大。

从 Docker Hub 上我们也可以找到[此镜像的 `Dockerfile` 文件](https://github.com/debuerreotype/docker-debian-artifacts/blob/fd138cb56a6a6a4fd9cb30c2acce9e8d9cccd28a/stretch/Dockerfile)，看下具体内容：

```bash
FROM scratch
ADD rootfs.tar.xz /
CMD ["bash"]
```

步骤与我们上面提到的完全符合, 不再进行展开了。

以上便详细解释了 Docker 镜像是什么：它其实是一组按照规范进行组织的分层文件，各层互不影响，并且每层的操作都将记录在 `history` 中。

## Docker 镜像的作用

从前面的讲述中，我们可以看到镜像中包含了一个完整的 `rootfs` ，在我们使用 `docker run` 命令时，便将指定镜像中的各层和配置组织起来共同启动一个新的容器；而在容器中，我们可以随意进行操作（包括读写）。

所以Docker 镜像的主要作用是：

- 为启动容器提供必要的文件；
- 记录了各层的操作和配置等。

## 容器和镜像的区别及联系

这里可以直接得出一个很直观的结论了。

镜像就是一系列文件和配置的组合，它是静态的，只读的，不可修改的； 而容器由镜像而来，但它是可操作的，是动态的，可修改的。

## Docker 镜像常规管理操作

Docker 由于不断增加新功能，为了方便，在后续版本中便对命令进行了分组。对镜像相关的命令都放到了 `docker image` 组内：

```bash
/ # docker image
Usage:  docker image COMMAND
Manage images
Commands:
  build       Build an image from a Dockerfile
  history     Show the history of an image
  import      Import the contents from a tarball to create a filesystem image
  inspect     Display detailed information on one or more images
  load        Load an image from a tar archive or STDIN
  ls          List images
  prune       Remove unused images
  pull        Pull an image or a repository from a registry
  push        Push an image or a repository to a registry
  rm          Remove one or more images
  save        Save one or more images to a tar archive (streamed to STDOUT by default)
  tag         Create a tag TARGET_IMAGE that refers to SOURCE_IMAGE
Run 'docker image COMMAND --help' for more information on a command.
```

对于我们开始时对镜像进行分析的操作，我们可以直接通过 `docker inspect debian` 直接拿到它的配置信息。

`pull`, `push`, `tag` 这三个子命令与和镜像仓库的交互比较相关，可以结合前面 `RepoTags` 理解。

`save` 和 `load` 是将镜像保存到文件系统上及从文件系统中导入 Docker 中。

`build` 命令会在接下来详细说明，剩余命令都比较简单直观了。

## 如何构建 Docker 镜像

前面详细讲述了 Docker 镜像是什么，以及简单介绍了常用的 Docker 镜像管理命令。那如何构建一个 Docker 镜像呢？通常情况下，有两种办法可以用于构建镜像（但并不只有这两种办法，以后再开 chat 来单独讲）。

### 从容器创建

还是以 debian 镜像为例，使用官方的 debian 镜像，启动一个容器：

```bash
/ # docker run --rm -it debian
[email protected]:/# toilet
bash: toilet: command not found
```

容器启动后，我们输入 `toilet` 来查看当前是否有 `toilet` 这个命令。 这是一个能将输入的字符串以更大的文本输出的命令行工具。

看上面的输入，当前的 PATH 中并没有该命令。我们使用 `apt` 进行安装。

```bash
[email protected]:/# apt update
Get:1 http://security-cdn.debian.org/debian-security stretch/updates InRelease [94.3 kB]
Ign:2 http://cdn-fastly.deb.debian.org/debian stretch InRelease
Get:5 http://security-cdn.debian.org/debian-security stretch/updates/main amd64 Packages [489 kB]
Get:3 http://cdn-fastly.deb.debian.org/debian stretch-updates InRelease [91.0 kB]         
Get:4 http://cdn-fastly.deb.debian.org/debian stretch Release [118 kB]
Get:6 http://cdn-fastly.deb.debian.org/debian stretch-updates/main amd64 Packages [31.7 kB]
Get:7 http://cdn-fastly.deb.debian.org/debian stretch Release.gpg [2434 B]
Get:8 http://cdn-fastly.deb.debian.org/debian stretch/main amd64 Packages [7082 kB]
Fetched 7909 kB in 3s (2285 kB/s)
Reading package lists... Done
Building dependency tree
Reading state information... Done
All packages are up to date.
[email protected]:/# apt install toilet -y
Reading package lists... Done
Building dependency tree
Reading state information... Done
The following additional packages will be installed:
  libcaca0 libslang2 toilet-fonts
Suggested packages:
  figlet
The following NEW packages will be installed:
  libcaca0 libslang2 toilet toilet-fonts
0 upgraded, 4 newly installed, 0 to remove and 0 not upgraded.
Need to get 1595 kB of archives.
...
Setting up toilet-fonts (0.3-1.1) ...
Setting up libslang2:amd64 (2.3.1-5) ...
Setting up libcaca0:amd64 (0.99.beta19-2+b2) ...
Setting up toilet (0.3-1.1) ...
update-alternatives: using /usr/bin/figlet-toilet to provide /usr/bin/figlet (figlet) in auto mode
Processing triggers for libc-bin (2.24-11+deb9u4) ...
```

可以看到，安装已经完成，我们在终端下输入 `toilet docker` 来查看下效果：

```bash
[email protected]:/# toilet docker
     #                #                   
  mmm#   mmm    mmm   #   m   mmm    m mm 
 #" "#  #" "#  #"  "  # m"   #"  #   #"  "
 #   #  #   #  #      #"#    #""""   #    
 "#m##  "#m#"  "#mm"  #  "m  "#mm"   #    
[email protected]:/#
```

该命令已经安装完成，并工作良好。现在我们使用当前容器来创建一个包含 `toilet` 命令的 Docker 镜像。

Docker 提供了一个命令 `docker container commit` 用于从容器创建一个镜像（当前也可以使用 `docker commit` ）。

```bash
/ # docker ps
CONTAINER ID        IMAGE               COMMAND             CREATED             STATUS              PORTS               NAMES          
daccf1e9155b        debian              "bash"              19 minutes ago      Up 19 minutes                           kind_lamport
/ # docker container commit -m "install toilet" daccf1e9155b local/debian:toilet
sha256:9ca72f9dcedbc7cf3f8643915184b6fbcba81fc207f1d45b0f872263ab9cc12c
/ # docker image ls
REPOSITORY          TAG                 IMAGE ID            CREATED             SIZE
local/debian        toilet              9ca72f9dcedb        15 seconds ago      121MB
debian              latest              8d31923452f8        5 days ago          101MB
```

直接将当前容器的 ID 传递给 `docker container commit` 作为参数，并提供一个新的镜像名称便可创建一个新的镜像（传递名称是为了方便使用，即使不传递名称也可以创建镜像）。

使用新的镜像来启动一个容器进行验证：

```bash
/ # docker run --rm -it local/debian:toilet 
[email protected]:/# toilet debian
     #         #        "                 
  mmm#   mmm   #mmm   mmm     mmm   m mm  
 #" "#  #"  #  #" "#    #    "   #  #"  # 
 #   #  #""""  #   #    #    m"""#  #   # 
 "#m##  "#mm"  ##m#"  mm#mm  "mm"#  #   # 
```

可以看到 `toilet` 已经存在。从容器创建镜像的目的达成。

### 从 Dockerfile 创建

Docker 提供了一种可根据配置文件构建镜像的方式，该配置文件通常命名为 `Dockerfile`。我们将刚才创建镜像的过程以 Dockerfile 进行描述。

```bash
/ # mkdir toilet       
/ # cd toilet/
/toilet # vi Dockerfile
/toilet # cat Dockerfile 
FROM debian
RUN apt update
RUN apt install -y toilet
```

Dockerfile 语法是固定的，但本篇不会对全部语法逐个解释，如有兴趣可查阅[官方文档](https://docs.docker.com/engine/reference/builder/#usage)。接下来使用该 Dockerfile 构建镜像。

```bash
/toilet # docker image build -t local/debian:toilet-using-dockerfile .                                          
Sending build context to Docker daemon   2.048kB       
Step 1/3 : FROM debian                 
 ---> 8d31923452f8                                                             
Step 2/3 : RUN apt update                                                                                       
 ---> Running in 9ab1f635aa05                  
WARNING: apt does not have a stable CLI interface. Use with caution in scripts.
Get:1 http://security-cdn.debian.org/debian-security stretch/updates InRelease [94.3 kB]
Ign:2 http://cdn-fastly.deb.debian.org/debian stretch InRelease
...
Reading package lists...                                                                                 
Building dependency tree...                                                                       
Reading state information...                                                                   
All packages are up to date.
Removing intermediate container 9ab1f635aa05
 ---> e6923f4d4e72
Step 3/3 : RUN apt install -y toilet
 ---> Running in ac1eeb29c4da
...
Processing triggers for libc-bin (2.24-11+deb9u4) ...
Setting up toilet-fonts (0.3-1.1) ...
Setting up libslang2:amd64 (2.3.1-5) ...
Setting up libcaca0:amd64 (0.99.beta19-2+b2) ...
Setting up toilet (0.3-1.1) ...
update-alternatives: using /usr/bin/figlet-toilet to provide /usr/bin/figlet (figlet) in auto mode              
Processing triggers for libc-bin (2.24-11+deb9u4) ...
Removing intermediate container ac1eeb29c4da
 ---> 267c669f183f
Successfully built 267c669f183f
Successfully tagged local/debian:toilet-using-dockerfile 
/toilet # docker image ls local/debian
REPOSITORY          TAG                       IMAGE ID            CREATED             SIZE
local/debian        toilet-using-dockerfile   267c669f183f        5 minutes ago       121MB
local/debian        toilet                    9ca72f9dcedb        26 minutes ago      121MB
```

使用 `-t` 参数来指定新生成镜像的名称，并且我们也可以看到该镜像已经构建成功。同样的使用该镜像创建容器进行测试：

```bash
/toilet # docker run --rm -it local/debian:toilet-using-dockerfile
[email protected]:/# toilet debian
     #         #        "                 
  mmm#   mmm   #mmm   mmm     mmm   m mm  
 #" "#  #"  #  #" "#    #    "   #  #"  # 
 #   #  #""""  #   #    #    m"""#  #   # 
 "#m##  "#mm"  ##m#"  mm#mm  "mm"#  #   # 
```

也都验证成功。如果你重复执行 `docker build` 命令的话，会看到有 `cache` 字样的输出，这是因为 Docker 为了提高构建镜像的效率，对已经构建过的每层进行了缓存，后面的内容会再讲到缓存相关的内容。

以上便是两种最常见构建容器镜像的方法了。其他办法之后开 chat 单独再聊。

## 逐步分解构建 Docker 镜像的最佳实践

### 从容器构建 VS 从 Dockerfile 构建

通过上面的介绍也可以看到，从容器构建很简单很直接，从 Dockerfile 构建则需要你描述出来每一步所做内容。

但是，如果对构建过程会有修改，或者是想要可维护，可记录，可追溯，那还是选择 Dockerfile 更为恰当。

### 以一个 Spring Boot 的项目为例

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

这里虽然以 Spring Boot 项目为例，但你如果对 Spring Boot 不熟悉的话也完全不影响后续内容，这里并不涉及 Spring Boot 的任何知识。你只需要知道对于这个项目而言，需要先装依赖，构建，才能运行。

那我们来看看一般情况下，对于这样的项目 `Dockerfile` 的内容是什么样的。

### 利用缓存

```bash
FROM debian
COPY . /app
RUN apt update
RUN apt install -y openjdk-8-jdk
CMD [ "java", "-jar", "/app/target/gs-spring-boot-0.1.0.jar" ]
```

这是一种比较典型的，在本地先构建好之后，再复制到容器镜像中。注意，由于 `debian` 镜像默认没有 Java 环境，所以还需要有 `apt`/`apt-get` 来安装 Java 环境。

那这样的 `Dockerfile` 有问题吗？有。

前面我们提到了，如果你对同样内容的 `Dockerfile` 执行两次 `docker build` 命令的话，会看到有 `cache` 字样的输出，这是因为 Docker 的 build 系统内置了缓存的逻辑，在构建时，会检查当前要构建的内容是否已经被缓存，如果被缓存则直接使用，否则重新构建，并且后续的缓存也将失效。

对于一个正常的项目而言，源代码的更新是最为频繁的。所以看上面的 `Dockerfile` 你会发现 `COPY . /app` 这一行，很容易就会让缓存失效，从而导致后面的缓存也都失效。

对此 `Dockerfile` 进行改进：

```bash
FROM debian
RUN apt update
RUN apt install -y openjdk-8-jdk
COPY . /app
CMD [ "java", "-jar", "/app/target/gs-spring-boot-0.1.0.jar" ]
```

第一个实践指南： **为了更有效的利用构建缓存，将更新最频繁的步骤放在最后面** 这样在之后的构建中，前三步都可以利用缓存。你可以运行多次 `docker build` 以进行验证。

### 部分拷贝

在项目变大，或者是项目中其他目录，比如 `docs` 目录内容很大时，根据前面对镜像相关的说明，直接使用 `COPY . /app` 会把所有内容拷贝至镜像中，导致镜像变大。

而对于我们要构建的镜像而言，那些文件是不必要的，所以我们可以将 `Dockerfile` 改成这样：

```bash
FROM debian
RUN apt update
RUN apt install -y openjdk-8-jdk
COPY target/gs-spring-boot-0.1.0.jar /app/
CMD [ "java", "-jar", "/app/gs-spring-boot-0.1.0.jar" ]
```

第二个实践指南： **避免将全部内容拷贝至镜像中, 至保留需要的内容即可** 。当然除去修改 `Dockerfile` 文件外，也可以通过修改 `.dockerignore` 文件来完成类似的事情。

`docker build` 的过程是先加载 `.dockerignore` 文件，然后才按照 `Dockerfile` 进行构建，`.dockerignore` 的用法与 `.gitignore` 类似，排除掉你不想要的文件即可。

### 防止包缓存过期

上面我们已经提到了， `docker build` 可以利用缓存，但你有没有考虑到，如果使用我们前面的 `Dockerfile`，当你机器上需要构建多个不同项目的镜像，或者是需要安装的依赖发生变化的时候，缓存可能就不是我们想要的了。

比如说，我想安装一个最新版的 `vim` 在镜像中，可以简单的修改第三行为 `RUN apt install -y openjdk-8-jdk vim` ，但由于 `RUN apt update` 是被缓存的，所以我无法安装到最新版本的 `vim` 。

```bash
FROM debian
RUN apt update && apt install -y openjdk-8-jdk
COPY target/gs-spring-boot-0.1.0.jar /app/
CMD [ "java", "-jar", "/app/gs-spring-boot-0.1.0.jar" ]
```

第三个实践指南： **将包管理器的缓存生成与安装包的命令写到一起可防止包缓存过期**

### 谨慎使用包管理器

了解 `apt`/`apt-get` 的朋友应该知道，在使用 `apt`/`apt-get` 安装包的时候，它会自动增加一些推荐安装的包，并且一同下载。但那些包对我们镜像中跑应用程序而言无关紧要。它有一个 `--no-install-recommends` 的选项可以避免安装那些推荐的包。

我们先来看下是否使用此选项的区别，我启动一个 `debian` 的容器进行测试：

```bash
[email protected]:/# apt install  --no-install-recommends openjdk-8-jdk | grep 'additional disk space will be used'
...
After this operation, 344 MB of additional disk space will be used.
^C
[email protected]:/# apt install openjdk-8-jdk | grep 'additional disk space will be used'
...
After this operation, 548 MB of additional disk space will be used.
^C
```

可以看到如果增加了 `--no-install-recommends` 选项的话，可以减少 200M 左右磁盘占用。

所以 `Dockerfile` 可以修改为：

```bash
FROM debian
RUN apt update && apt install -y --no-install-recommends openjdk-8-jdk
COPY target/gs-spring-boot-0.1.0.jar /app/
CMD [ "java", "-jar", "/app/gs-spring-boot-0.1.0.jar" ]
```

此时构建镜像，我们来与之前的镜像做下对比：

```bash
(MoeLove) ➜  docker image ls local/spring-boot
REPOSITORY          TAG                 IMAGE ID            CREATED             SIZE
local/spring-boot   4                   716523c83a26        3 minutes ago       497MB
local/spring-boot   2                   178dacdaf015        9 hours ago         600MB
```

可以很明显看到镜像明显变小了。

接下来还有个值得注意的地方。我们一开始执行了 `apt update` 这个命令，它主要是在缓存源信息。而对于我们构建所需镜像时，这没有必要。我们选择将这些缓存文件删掉。

启动一个新的容器验证下：

```bash
(MoeLove) ➜  docker run --rm -it debian
[email protected]:/# apt -qq  update 
All packages are up to date.
[email protected]:/# du -sh /var/lib/apt/lists/
16M     /var/lib/apt/lists/
[email protected]:/# 
```

可以看到有 16M 左右的大小，我们修改 `Dockerfile` 增加删除操作：

```bash
FROM debian
RUN apt update && apt install -y --no-install-recommends openjdk-8-jdk \
        && rm -rf /var/lib/apt/lists/*  
COPY target/gs-spring-boot-0.1.0.jar /app/
CMD [ "java", "-jar", "/app/gs-spring-boot-0.1.0.jar" ]
```

对比使用这个 `Dockerfile` 构建镜像的镜像大小

```bash
(MoeLove) ➜  docker image ls local/spring-boot                    
REPOSITORY          TAG                 IMAGE ID            CREATED             SIZE                     
local/spring-boot   4-2                 ac272f3dcac2        24 seconds ago      481MB                    
local/spring-boot   4                   716523c83a26        37 minutes ago      497MB                    
local/spring-boot   2                   178dacdaf015        10 hours ago        600MB
```

可以看到小了 16M 左右。

第四个实践指南： **谨慎使用包管理器，不安装非必要的包，注意清理包管理器缓存文件** 。

### 选择合适的基础镜像

Docker Hub 上提供了很多 [官方镜像](https://hub.docker.com/search/?q=&type=image&image_filter=official) 这些镜像的构建基本上都经过了大量的优化，尽可能缩小镜像体积，减少镜像层数。

当我们构建镜像的时候，不妨先查看官方镜像是否有满足需求的镜像可以作为基础镜像。Java 运行环境官方镜像是有提前提供的 [openjdk](https://hub.docker.com/_/openjdk) 我们可以在 GitHub 上找到它构建镜像的 [Dockerfile](https://github.com/docker-library/openjdk/blob/b8ce9eff38451de3282b2eb2bcd8b520fb95e1ce/8/jdk/Dockerfile) 可以看到其中的一些构建过程与我们前面所说的实践方式相符。

我们选择 Docker 官方 `openjdk` 镜像来作为基础镜像，`Dockerfile` 可以改写为：

```bash
FROM openjdk:8-jdk-stretch
COPY target/gs-spring-boot-0.1.0.jar /app/
CMD [ "java", "-jar", "/app/gs-spring-boot-0.1.0.jar" ]
```

`openjdk` 有很多不同的 tag 比如 `8-jdk-stretch` `8-jre-stretch` 以及 `8-jre-alpine` 之类的，具体的可以在 [openjdk 的 tag 页面](https://hub.docker.com/_/openjdk?tab=tags)查看。

我们其实只想要一个 Java 的运行环境，所以选择一个基于 [Alpine Linux](https://alpinelinux.org/) 的超小的镜像 `openjdk:8-jre-alpine` 这样 `Dockerfile` 可以改写为:

```bash
FROM openjdk:8-jre-alpine
COPY target/gs-spring-boot-0.1.0.jar /app/
CMD [ "java", "-jar", "/app/gs-spring-boot-0.1.0.jar" ]
```

分别用上面的 `Dockerfile` 构建镜像，可以看到镜像大小

```bash
(MoeLove) ➜  docker image ls local/spring-boot                           
REPOSITORY          TAG                 IMAGE ID            CREATED             SIZE
local/spring-boot   5-1                 b423dfc8d995        23 minutes ago      103MB
local/spring-boot   5                   7158d42a6a87        25 minutes ago      643MB
local/spring-boot   4-2                 ac272f3dcac2        4 hours ago         481MB
local/spring-boot   4                   716523c83a26        5 hours ago         497MB
local/spring-boot   2                   178dacdaf015        14 hours ago        600MB
```

很明显，使用 `openjdk:8-jre-alpine` 后，镜像大小只有 103M 比之前的镜像小了很多。

第五个实践指南： **尽可能选择官方镜像，看实际需求进行最终选择** 这样说的原因，主要是因为 Alpine Linux 并非基于 glibc 的，而是基于 musl 的，如果是 Python 的项目，请实际测试下性能损失再决定是否选择 Alpine Linux （[这里](http://moelove.info/docker-python-perf/)是我做的一份关于 Python 各镜像主要的性能对比，有需要可以参考）

### 保持构建环境一致

在前面的实践中，我们都是先本地构建好之后，才 `COPY` 进去的，这容易导致不同用户构建出的镜像可能不同。所以我们将构建过程写入到 `Dockerfile`:

```bash
FROM maven:3.6.1-jdk-8-alpine
WORKDIR /app
COPY pom.xml /app/
COPY src /app/src
RUN mvn -e -B package
CMD [ "java", "-jar", "/app/target/gs-spring-boot-0.1.0.jar" ]
```

这样所有人都可以使用相同的 `Dockerfile` 构建出相同的镜像了。

但我们也会发现一个问题，在 `mvn -e -B package` 这一步耗费的时间特别长，因为它需要先拉取依赖才能进行构建。而对于项目开发而言，代码变更比依赖变更更加频繁，为了能加快构建速度，有效的利用缓存，我们将解决依赖与构建分成两步。

```bash
FROM maven:3.6.1-jdk-8-alpine
WORKDIR /app
COPY pom.xml /app/
RUN mvn dependency:go-offline
COPY src /app/src
RUN mvn -e -B package
CMD [ "java", "-jar", "/app/target/gs-spring-boot-0.1.0.jar" ]
```

这样， **即使业务代码发生改变，也不需要重新解决依赖，可有效的利用了缓存，加快构建的速度** 。

当然，现在我们构建的镜像中，还是包含着项目的源代码，这其实并非我们所需要的。那么我们可以使用 **多阶段构建** 来解决这个问题。`Dockerfile` 可以修改为：

```bash
FROM maven:3.6.1-jdk-8-alpine AS builder
WORKDIR /app
COPY pom.xml /app/
RUN mvn dependency:go-offline
COPY src /app/src
RUN mvn -e -B package
FROM openjdk:8-jre-alpine
COPY --from=builder /app/target/gs-spring-boot-0.1.0.jar /
CMD [ "java", "-jar", "/gs-spring-boot-0.1.0.jar" ]
```

当然，多阶段构建也并不只是为了缩小镜像体积；我们可以使用指定构建阶段，以满足多种不同的镜像需求。

`Dockerfile` 可以修改为：

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

我们可以使用如下的命令来构建不同阶段的镜像；

```bash
# 构建用于开发的镜像
(MoeLove) ➜  docker build --target dev -t local/spring-boot:6-4-dev .    
# 构建用于生产部署的镜像
(MoeLove) ➜  docker build -t local/spring-boot:6-4 .    
```

我们来看看在这个过程中镜像大小的变化：

```bash
(MoeLove) ➜  docker image ls local/spring-boot                           
REPOSITORY          TAG                 IMAGE ID            CREATED             SIZE
local/spring-boot   6-4-dev             f47a322c9de3        6 seconds ago       250MB
local/spring-boot   6-4                 2ab6215ff05e        3 minutes ago       103MB
local/spring-boot   6-3                 2ab6215ff05e        3 minutes ago       103MB
local/spring-boot   6-2                 2b3d3f923e05        4 minutes ago       225MB
local/spring-boot   6                   f96bea38825f        2 hours ago         188MB
```

## 如何提升构建效率

在构建 Docker 镜像的最佳实践部分中，我们提到了很多方法，比如利用缓存；减少安装依赖等，这些都可以提升构建效率。

我们还提到了多阶段构建，这是一种很方便而且很灵活的方式。但多阶段构建，在默认情况下是顺序构建；对于现在的新版本 18.09+ 以及即将发布的 19.03 版本，我们多了一种更有效的办法 `buildkit`。

通过添加环境变量 `DOCKER_BUILDKIT=1` 或者在 Docker 的配置文件 `/etc/docker/daemon.json` 中添加如下配置：

```bash
"features": {
    "buildkit": true
}
```

开启使用 `buildkit`。

`buildkit` 在多阶段构建时，可进行并行构建，可大大提升了构建效率。

前面主要讲述的内容为：Docker 镜像是什么，以及构建 Docker 镜像的最佳实践，最后简单提到了 `buildkit`。
