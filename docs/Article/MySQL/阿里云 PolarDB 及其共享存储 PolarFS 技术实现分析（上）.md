# 阿里云 PolarDB 及其共享存储 PolarFS 技术实现分析（上）

PolarDB 是阿里云基于 MySQL 推出的云原生数据库（Cloud Native Database）产品，通过将数据库中计算和存储分离，多个计算节点访问同一份存储数据的方式来解决目前 MySQL 数据库存在的运维和扩展性问题；通过引入 RDMA 和 SPDK 等新硬件来改造传统的网络和 IO 协议栈来极大提升数据库性能。代表了未来数据库发展的一个方向。本系列共 2 篇文章，主要分析为什么会出现 PolarDB 以及其技术实现。

由于 PolarDB 并不开源，因此只能基于阿里云公开的技术资料进行解读。这些资料包括从去年下半年开始陆续在阿里云栖社区、云栖大会等场合发布的 PolarDB 相关资料，以及今年以来公开的 PolarDB 后端共享存储 PolarFS 相关文章。

PolarDB 出现背景

MySQL 云服务遇到的问题

首先来了解下为什么会出现 PolarDB。阿里云数据库团队具备国内领先的技术能力，为 MySQL 等数据库在国内的推广起到了很大的作用。在阿里云上也维护了非常庞大的 MySQL 云服务（RDS）集群，但也遇到了很多棘手的问题。举例如下：

- 实例数据量太大，单实例几个 TB 的数据，这样即使使用 xtrabackup 物理备份，也需要很长的备份时间，且备份期间写入量大的话可能导致 redo 日志被覆盖引起备份失败；
- 大实例故障恢复需要重建时，耗时太长，影响服务可用性（此时存活节点也挂了，那么完蛋了）。时间长有 2 个原因，一是备份需要很长时间，二是恢复的时候回放 redo 也需要较长时间；
- 大实例做只读扩展麻烦，因为只读实例的数据是单独一份的，所以也需要通过备份来重建；
- RDS 实例集群很大，包括成千上万个实例，可能同时有很多实例同时在备份，会占用云服务巨大的网络和 IO 带宽，导致云服务不稳定；
- 云服务一般使用云硬盘，导致数据库的性能没有物理机实例好，比如 IO 延时过高；
- 主库写入量大的时候，会导致主从复制延迟过大，semi-sync/半同步复制也没法彻底解决，这是由于 mysql 基于 binlog 复制，需要走完整的 mysql 事务处理流程。
- 对于需要读写分离，且要求部署多个只读节点的用户，最明显的感觉就是每增加一个只读实例，成本是线性增长的。

其实不仅仅是阿里云 RDS，网易云上的 RDS 服务也有数千个实例，同样遇到了类似的问题，我们是亲身经历而非感同身受。应该说就目前的 MySQL 技术实现方案，要解决上述任何一个问题都不是件容易的事情，甚至有几个问题是无法避免的。

现有解决方案及不足

那么，跳出 MySQL，是否有解决方案呢，分析目前业界的数据库和存储领域技术，可以发现基于共享存储是个可选的方案，所谓数据库共享存储方案指的是 RDS 实例（一般指一主一从的高可用实例）和只读实例共享同一份数据，这样在实例故障或只读扩展时就无需拷贝数据了，只需简单得把故障节点重新拉起来，或者新建个只读计算节点即可，省时省力更省钱。共享存储可通过快照技术（snapshot/checkpoint）和写时拷贝（copy-on-write，COW）来解决数据备份和误操作恢复问题，将所需备份的数据量分摊到较长的一段时间内，而不需要瞬时完成，这样就不会导致多实例同时备份导致网络和 IO 数据风暴。下图就是一个典型的数据库共享存储方案，Primary 节点即数据库主节点，对外提供读写服务，Read Only 节点可以是 Primary 的灾备节点，也可以是对外提供只读服务的节点，他们共享一份底层数据。

![img](../assets/20181012175033a45a1419-5df7-4ec2-9601-43ece82896b8.jpg)

理想很丰满，但现实却很骨感，目前可用的共享存储方案寥寥无几，比如在 Hadoop 生态圈占统治地位的 HDFS，以及在通用存储领域风生水起的 Ceph，只是如果将其作为在线数据处理（OLTP）服务的共享存储，最终对用户呈现的性能是不可接受的。除此之外，还存在大量与现有数据库实现整合适配等问题。

PolarDB 实现方案

云原生数据库

说道云原生数据库，就不得不提 Aurora。其在 2014 年下半年发布后，轰动了整个数据库领域。Aurora 对 MySQL 存储层进行了大刀阔斧的改造，将其拆为独立的存储节点(主要做数据块存储，数据库快照的服务器)。上层的 MySQL 计算节点(主要做 SQL 解析以及存储引擎计算的服务器)共享同一个存储节点，可在同一个共享存储上快速部署新的计算节点，高效解决服务能力扩展和服务高可用问题。基于日志即数据的思想，大大减少了计算节点和存储节点间的网络 IO，进一步提升了数据库的性能。再利用存储领域成熟的快照技术，解决数据库数据备份问题。被公认为关系型数据库的未来发展方向之一。截止 2018 年上半年，Aurora 已经实现了多个计算节点同时提供写服务的能力，继续在云原生数据库上保持领先的地位。

不难推断，在 Aurora 发布 3 年后推出的 PolarDB，肯定对 Aurora 进行了深入的研究，并借鉴了很多技术实现方法。关于 Aurora 的分析，国内外，包括公司内都已进行了深入分析，本文不再展开描述。下面着重介绍 PolarDB 实现。我们采用先存储后计算的方式，先讲清楚 PolarFS 共享存储的实现，再分析 PolarDB 计算层如何适配 PolarFS。

PolarDB 架构

![img](../assets/201810121750331dd25433-6361-4349-9069-a7102623b6eb.png)

上图为 PolarFS 视角看到的 PolarDB 实现架构。一套 PolarDB 至少包括 3 个部分，分别为最底层的共享存储，与用户交互的 MySQL 节点，还有用户进行系统管理的 PolarCtrl。而其中 PolarFS 又可进一步拆分为 libpfs、PolarSwitch 和 ChunkServer。下面进行简单说明：

- MySQL 节点，即图中的 POLARDB，负责用户 SQL 解析、事务处理等数据库相关操作，扮演计算节点角色；
- libpfs 是一个用户空间文件系统库，提供 POSIX 兼容的文件操作 API 接口，嵌入到 PolarDB 负责数据库 IO（File IO）接入；
- PolarSwitch 运行在计算节点主机（Host）上，每个 Host 部署一个 PolarSwitch 的守护进程，其将数据库文件 IO 变换为块设备 IO，并发送到具体的后端节点（即 ChunkServer）；
- ChunkServer 部署在存储节点上，用于处理块设备 IO（Block IO）请求和节点内的存储资源分布；
- PolarCtrl 是系统的控制平面，PolarFS 集群的控制核心，所有的计算和存储节点均部署有 PolarCtrl 的 Agent。

PolarFS 的存储组织

与大多数存储系统一样，PolarFS 对存储资源也进行了多层封装和管理，PolarFS 的存储层次包括：Volume、Chunk 和 Block，分别对应存储领域中的数据卷，数据区和数据块，在有些系统中 Chunk 又被成为 Extent，均表示一段连续的块组成的更大的区域，作为分配的基本单位。一张图可以大致表现各层的关系：

![img](../assets/20181012175033932353c3-f60e-4824-82ab-fb726c962c6a.png)

**Volume** 当用户申请创建 PolarDB 数据库实例时，系统就会为该实例创建一个 Volume（卷，本文后续将这两种表达混用），每个卷都有多个 Chunk 组成，其大小就是用户指定的数据库实例大小，PolarDB 支持用户创建的实例大小范围是 10GB 至 100TB，满足绝大部分云数据库实例的容量要求。

跟其他传统的块设备一样，卷上的读写 IO 以 512B 大小对齐，对卷上同个 Chunk 的修改操作是原子的。当然，卷还是块设备层面的概念，在提供给数据库实例使用前，需在卷上格式化一个 PolarFS 文件系统（PFS）实例，跟 ext4、btrfs 一样，PFS 上也会在卷上存放文件系统元数据。这些元数据包括 inode、directory entry 和空闲块等对象。同时，PFS 也是一个日志文件系统，为了实现文件系统的元数据一致性，元数据的更新会首先记录在卷上的 Journal（日志）文件中，然后才更新指定的元数据。

跟传统文件系统不一样的是 PolarFS 是个共享文件系统即一个卷会被挂载到多个计算节点上，也就是说可能存在有多个客户端（挂载点）对文件系统进行读写和更新操作，所以 PolarFS 在卷上额外维护了一个 Paxos 文件。每个客户端在更新 Journal 文件前，都需要使用 Paxos 文件执行 Disk Paxos 算法实现对 Journal 文件的互斥访问。更详细的 PolarFS 元数据更新实现，后续单独作为一个小节。**Chunk** 前面提到，每个卷内部会被划分为多个 Chunk（区），区是数据分布的最小粒度，每个区都位于单块 SSD 盘上，其目的是利于数据高可靠和高可用的管理，详见后续章节。每个 Chunk 大小设置为 10GB，远大于其他类似的存储系统，例如 GFS 为 64MB，Linux LVM 的物理区（PE）为 4MB。这样做的目的是减少卷到区映射的元数据量大小（例如，100TB 的卷只包含 10K 个映射项）。一方面，全局元数据的存放和管理会更容易；另一方面，元数据可以全都缓存在内存中，避免关键 IO 路径上的额外元数据访问开销。

当然，Chunk 设置为 10GB 也有不足。当上层数据库应用出现区域级热点访问时，Chunk 内热点无法进一步打散，但是由于每个存储节点提供的 Chunk 数量往往远大于节点数量（节点:Chunk 在 1:1000 量级），PolarFS 支持 Chunk 的在线迁移，其上服务着大量数据库实例，因此可以将热点 Chunk 分布到不同节点上以获得整体的负载均衡。

在 PolarFS 上，卷上的每个 Chunk 都有 3 个副本，分布在不同的 ChunkServer 上，3 个副本基于 ParallelRaft 分布式一致性协议来保证数据高可靠和高可用。**Block**

在 ChunkServer 内，Chunk 会被进一步划分为 163,840 个 Block（块），每个块大小为 64KB。Chunk 至 Block 的映射信息由 ChunkServer 自行管理和保存。每个 Chunk 除了用于存放数据库数据的 Block 外，还包含一些额外 Block 用来实现预写日志（Write Ahead Log，WAL）。

需要注意的是，虽然 Chunk 被进一步划分为块，但 Chunk 内的各个 Block 在 SSD 盘是物理连续的。PolarFS 的 VLDB 文章里提到“Blocks are allocated and mapped to a chunk on demand to achieve thin provisioning”。thin provisioning 就是精简配置，是存储上常用的技术，就是用户创建一个 100GB 大小的卷，但其实在卷创建时并没有实际分配 100GB 存储空间给它，仅仅是逻辑上为其创建 10 个 Chunk，随着用户数据不断写入，PolarFS 不断分配物理存储空间供其使用，这样能够实现存储系统按需扩容，大大节省存储成本。

那么为何 PolarFS 要引入 Block 这个概念呢，其中一个是跟卷上的具体文件相关，我们知道一个文件系统会有多个文件，比如 InnoDB 数据文件\*.ibd。每个文件大小会动态增长，文件系统采用预分配（fallocate()）为文件提前分配更多的空间，这样在真正写数据的时无需进行文件系统元数据操作，进而优化了性能。显然，每次给文件分配一个 Chunk，即 10GB 空间是不合理的，64KB 或其倍数才是合适的值。上面提到了精简配置和预分配，看起来是冲突的方法，但其实是统一的，精简配置的粒度比预分配的粒度大，比如精简配置了 10GB，预分配了 64KB。这样对用户使用没有任何影响，同时还节省了存储成本。

PolarFS 组件解析

首先展示一张能够更加清晰描述与数据流相关的各个组件作用的示意图，并逐一对其进行解释。

![img](../assets/20181012175034d5fb0058-7b69-43ba-a25b-19a75f533ef0.png)

**libpfs** libpfs 是一个用户空间文件系统（即上图 User Space File System）库，负责数据库 IO（File IO）接入。更直观点，libpfs 提供了供计算节点/PolarDB 访问底层存储的 API 接口，进行文件读写和元数据更新等操作，如下图所示：

![img](../assets/20181012175034e664ea5a-6091-4efd-a3c6-dbb93b49cfe3.png)

pfs_mount()用于将指定卷上文件系统挂载到对应的数据库计算节点上，该操作会获取卷上的文件系统元数据信息，将其缓存在计算节点上，这些元数据信息包括目录树（the directory tree），文件映射表（the file mapping table）和块映射表（the block mapping table）等，其中目录树描述了文件目录层级结构信息，每个文件名对应的 inode 节点信息（目录项）。inode 节点信息就是文件系统中唯一标识一个文件的 FileID。文件映射表描述了该文件都有哪些 Block 组成。通过上图我们还发现了 pfs_mount_growfs()，该 API 可以让用户方便得进行数据库扩容，在对卷进行扩容后，通过调用该 API 将增加的空间映射到文件系统层。

![img](../assets/20181012175035369fb3c9-464d-488f-8264-e62e38d2e26f.png)

上图右侧的表描述了目录树中的某个文件的前 3 个块分别对应的是卷的第 348,1500 和 201 这几个块。假如数据库操作需要回刷一个脏页，该页在该表所属文件的偏移位置 128KB 处，也就是说要写该文件偏移 128KB 开始的 16KB 数据，通过文件映射表知道该写操作其实写的是卷的第 201 个块。这就是 lipfs 发送给 PolarSwitch 的请求包含的内容：volumeid，offset 和 len。其中 offset 就是 201\*64KB，len 就是 16KB。

**PolarSwitch** PolarSwitch 是部署在计算节点的 Daemon，即上图的 Data Router&Cache 模块，它负责接收 libpfs 发送而来的文件 IO 请求，PolarSwitch 将其划分为对应的一到多个 Chunk，并将请求发往 Chunk 所属的 ChunkServer 完成访问。具体来说 PolarSwitch 根据自己缓存的 volumeid 到 Chunk 的映射表，知道该文件请求属于那个 Chunk。请求如果跨 Chunk 的话，会将其进一步拆分为多个块 IO 请求。PolarSwitch 还缓存了该 Chunk 的三个副本分别属于那几个 ChunkServer 以及哪个 ChunkServer 是当前的 Leader 节点。PolarSwitch 只将请求发送给 Leader 节点。**ChunkServer** ChunkServer 部署在存储节点上，即上图的 Data Chunk Server，用于处理块 IO（Block IO）请求和节点内的存储资源分布。一个存储节点可以有多个 ChunkServer，每个 ChunkServer 绑定到一个 CPU 核，并管理一块独立的 NVMe SSD 盘，因此 ChunkServer 之间没有资源竞争。

ChunkServer 负责存储 Chunk 和提供 Chunk 上的 IO 随机访问。每个 Chunk 都包括一个 WAL，对 Chunk 的修改会先写 Log 再执行修改操作，保证数据的原子性和持久性。ChunkServer 使用了 3D XPoint SSD 和普通 NVMe SSD 混合型 WAL buffer，Log 会优先存放到更快的 3DXPoint SSD 中。

前面提到 Chunk 有 3 副本，这三个副本基于 ParallelRaft 协议，作为该 Chunk Leader 的 ChunkServer 会将块 IO 请求发送给 Follow 节点其他 ChunkServer）上，通过 ParallelRaft 一致性协议来保证已提交的 Chunk 数据不丢失。**PolarCtrl**

PolarCtrl 是系统的控制平面，相应地 Agent 代理被部署到所有的计算和存储节点上，PolarCtrl 与各个节点的交互通过 Agent 进行。PolarCtrl 是 PolarFS 集群的控制核心，后端使用一个关系数据库云服务来管理 PolarDB 的元数据。其主要职责包括：

- 监控 ChunkServer 的健康状况，包括剔除出现故障的 ChunkServer，维护 Chunk 多个副本的关系，迁移负载过高的 ChunkServer 上的部分 Chunk 等；
- Volume 创建及 Chunk 的布局管理，比如 Volume 上的 Chunk 应该分配到哪些 ChunkServer 上；
- Volume 至 Chunk 的元数据信息维护；
- 向 PolarSwitch 推送元信息缓存更新，比如因为计算节点执行 DDL 导致卷上文件系统元数据更新，这些更新可通过 PolarCtrl 推送给 PolarSwitch；
- 监控 Volume 和 Chunk 的 IO 性能，根据一定的规则进行迁移操作；
- 周期性地发起副本内和副本间的 CRC 数据校验。

本篇主要是介绍了 PolarDB 数据库及其后端共享存储 PolarFS 系统的基本架构和组成模块，是最基础的部分。下一篇重点分析 PolarFS 的数据 IO 流程，元数据更新流程，以及 PolarDB 数据库节点如何适配 PolarFS 这样的共享存储系统。
