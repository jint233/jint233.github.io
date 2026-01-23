# MySQL 主从复制

本文非常详细地介绍 MySQL 复制相关的内容，包括基本概念、复制原理、如何配置不同类型的复制(传统复制)等等。在此文章之后，还有几篇文章分别介绍 GTID 复制、半同步复制、实现 MySQL 的动静分离，以及 MySQL 5.7.17 引入的革命性功能：组复制(MGR)。

本文是 MySQL Replication 的基础，但却非常重要。对于 MySQL 复制，如何搭建它不是重点(因为简单，网上资源非常多)，如何维护它才是重点(网上资源不集中)。以下几个知识点是掌握 MySQL 复制所必备的：

1. 复制的原理
2. 将 master 上已存在的数据恢复到 slave 上作为基准数据
3. 获取 **正确的** binlog 坐标
4. **深入理解** `show slave status`中的一些状态信息

本文对以上内容都做了非常详细的说明。希望对各位初学、深入 MySQL 复制有所帮助。

mysql replication 官方手册：[https://dev.mysql.com/doc/refman/5.7/en/replication.html。](https://dev.mysql.com/doc/refman/5.7/en/replication.html%E3%80%82)

# 1.复制的基本概念和原理

mysql 复制是指从一个 mysql 服务器(MASTER)将数据 **通过日志的方式经过网络传送** 到另一台或多台 mysql 服务器(SLAVE)，然后在 slave 上重放(replay 或 redo)传送过来的日志，以达到和 master 数据同步的目的。

它的工作原理很简单。首先 **确保 master 数据库上开启了二进制日志，这是复制的前提**。

- 在 slave 准备开始复制时，首先 **要执行 change master to 语句设置连接到 master 服务器的连接参数**，在执行该语句的时候要提供一些信息，包括如何连接和要从哪复制 binlog，这些信息在连接的时候会记录到 slave 的 datadir 下的 master.info 文件中，以后再连接 master 的时候将不用再提供这新信息而是直接读取该文件进行连接。

- 在 slave 上有两种线程， 分别是 IO 线程和 SQL 线程

  - IO 线程用于连接 master，监控和接受 master 的 binlog。当启动 IO 线程成功连接 master 时，**master 会同时启动一个 dump 线程**，该线程将 slave 请求要复制的 binlog 给 dump 出来，之后 IO 线程负责监控并接收 master 上 dump 出来的二进制日志，当 master 上 binlog 有变化的时候，IO 线程就将其复制过来并写入到自己的中继日志(relay log)文件中。
  - slave 上的另一个线程 SQL 线程用于监控、读取并重放 relay log 中的日志，将数据写入到自己的数据库中。如下图所示。

站在 slave 的角度上看，过程如下：

![img](../assets/733013-20180524163346938-787080496.png)

站在 master 的角度上看，过程如下(默认的异步复制模式，前提是设置了`sync_binlog=1`，否则 binlog 刷盘时间由操作系统决定)：

![img](../assets/733013-20180610221451539-1794738810.png)

所以，可以认为复制大致有三个步骤：

1. 数据修改写入 master 数据库的 binlog 中。
2. slave 的 IO 线程复制这些变动的 binlog 到自己的 relay log 中。
3. slave 的 SQL 线程读取并重新应用 relay log 到自己的数据库上，让其和 master 数据库保持一致。

从复制的机制上可以知道，在复制进行前，slave 上必须具有 master 上部分完整内容作为复制基准数据。例如，master 上有数据库 A，二进制日志已经写到了 pos1 位置，那么在复制进行前，slave 上必须要有数据库 A，且如果要从 pos1 位置开始复制的话，还必须有和 master 上 pos1 之前完全一致的数据。如果不满足这样的一致性条件，那么在 replay 中继日志的时候将不知道如何进行应用而导致数据混乱。**也就是说，复制是基于 binlog 的 position 进行的，复制之前必须保证 position 一致。** (注：这是传统的复制方式所要求的)

可以选择对哪些数据库甚至数据库中的哪些表进行复制。**默认情况下，MySQL 的复制是异步的。slave 可以不用一直连着 master，即使中间断开了也能从断开的 position 处继续进行复制。** MySQL 5.6 对比 MySQL 5.5 在复制上进行了很大的改进，主要包括支持 GTID(Global Transaction ID,全局事务 ID)复制和多 SQL 线程并行重放。GTID 的复制方式和传统的复制方式不一样，通过全局事务 ID，它不要求复制前 slave 有基准数据，也不要求 binlog 的 position 一致。

MySQL 5.7.17 则提出了组复制(MySQL Group Replication,MGR)的概念。像数据库这样的产品，必须要尽可能完美地设计一致性问题，特别是在集群、分布式环境下。Galera 就是一个 MySQL 集群产品，它支持多主模型(多个 master)，但是当 MySQL 5.7.17 引入了 MGR 功能后，Galera 的优势不再明显，甚至 MGR 可以取而代之。MGR 为 MySQL 集群中多主复制的很多问题提供了很好的方案，可谓是一项革命性的功能。

复制和二进制日志息息相关，所以学习本章必须先有二进制日志的相关知识。

# 2.复制的好处

围绕下面的拓扑图来分析：

![img](../assets/733013-20180524173723814-389803553.png)

主要有以下几点好处： **1.提供了读写分离的能力。** replication 让所有的 slave 都和 master 保持数据一致，因此外界客户端可以从各个 slave 中读取数据，而写数据则从 master 上操作。也就是实现了读写分离。

需要注意的是，为了保证数据一致性，**写操作必须在 master 上进行**。

通常说到读写分离这个词，立刻就能意识到它会分散压力、提高性能。**2.为 MySQL 服务器提供了良好的伸缩(scale-out)能力。** 由于各个 slave 服务器上只提供数据检索而没有写操作，因此"随意地"增加 slave 服务器数量来提升整个 MySQL 群的性能，而不会对当前业务产生任何影响。

之所以"随意地"要加上双引号，是因为每个 slave 都要和 master 建立连接，传输数据。如果 slave 数量巨多，master 的压力就会增大，网络带宽的压力也会增大。**3.数据库备份时，对业务影响降到最低。** 由于 MySQL 服务器群中所有数据都是一致的(至少几乎是一致的)，所以在需要备份数据库的时候可以任意停止某一台 slave 的复制功能(甚至停止整个 mysql 服务)，然后从这台主机上进行备份，这样几乎不会影响整个业务(除非只有一台 slave，但既然只有一台 slave，说明业务压力并不大，短期内将这个压力分配给 master 也不会有什么影响)。**4.能提升数据的安全性。** 这是显然的，任意一台 mysql 服务器断开，都不会丢失数据。即使是 master 宕机，也只是丢失了那部分还没有传送的数据(异步复制时才会丢失这部分数据)。**5.数据分析不再影响业务。**

需要进行数据分析的时候，直接划分一台或多台 slave 出来专门用于数据分析。这样 OLTP 和 OLAP 可以共存，且几乎不会影响业务处理性能。

# 3.复制分类和它们的特性

MySQL 支持两种不同的复制方法：传统的复制方式和 GTID 复制。MySQL 5.7.17 之后还支持组复制(MGR)。

- (1).传统的复制方法要求复制之前，slave 上必须有基准数据，且 binlog 的 position 一致。
- (2).GTID 复制方法不要求基准数据和 binlog 的 position 一致性。GTID 复制时，master 上只要一提交，就会立即应用到 slave 上。这极大地简化了复制的复杂性，且更好地保证 master 上和各 slave 上的数据一致性。

从数据同步方式的角度考虑，MySQL 支持 4 种不同的同步方式：同步(synchronous)、半同步(semisynchronous)、异步(asynchronous)、延迟(delayed)。所以对于复制来说，就分为同步复制、半同步复制、异步复制和延迟复制。

## 3.1 同步复制

客户端发送 DDL/DML 语句给 master，master 执行完毕后还需要 **等待所有的 slave 都写完了 relay log 才认为此次 DDL/DML 成功，然后才会返回成功信息给客户端**。同步复制的问题是 master 必须等待，所以延迟较大，在 MySQL 中不使用这种复制方式。

![img](../assets/733013-20180524204948187-2045181991.png)

例如上图中描述的，只有 3 个 slave 全都写完 relay log 并返回 ACK 给 master 后，master 才会判断此次 DDL/DML 成功。

## 3.2 半同步复制

客户端发送 DDL/DML 语句给 master，master 执行完毕后 **还要等待一个 slave 写完 relay log 并返回确认信息给 master，master 才认为此次 DDL/DML 语句是成功的，然后才会发送成功信息给客户端**。半同步复制只需等待一个 slave 的回应，且等待的超时时间可以设置，超时后会自动降级为异步复制，所以在局域网内(网络延迟很小)使用半同步复制是可行的。

![img](../assets/733013-20180524205148967-868029789.png)

例如上图中，只有第一个 slave 返回成功，master 就判断此次 DDL/DML 成功，其他的 slave 无论复制进行到哪一个阶段都无关紧要。

## 3.3 异步复制

客户端发送 DDL/DML 语句给 master，**master 执行完毕立即返回成功信息给客户端，而不管 slave 是否已经开始复制**。这样的复制方式导致的问题是，当 master 写完了 binlog，而 slave 还没有开始复制或者复制还没完成时，**slave 上和 master 上的数据暂时不一致，且此时 master 突然宕机，slave 将会丢失一部分数据。如果此时把 slave 提升为新的 master，那么整个数据库就永久丢失这部分数据。**![img](../assets/733013-20180524205215240-203795747.png)

## 3.4 延迟复制

顾名思义，延迟复制就是故意让 slave 延迟一段时间再从 master 上进行复制。

# 4.配置一主一从

此处先配置默认的异步复制模式。由于复制和 binlog 息息相关，如果对 binlog 还不熟悉，请先了解 binlog，见：[详细分析二进制日志](https://www.cnblogs.com/f-ck-need-u/p/9001061.html#blog5)。

mysql 支持一主一从和一主多从。但是每个 slave 必须只能是一个 master 的从，否则从多个 master 接受二进制日志后重放将会导致数据混乱的问题。

以下是一主一从的结构图：

![img](../assets/733013-20180528163847611-1424365065.png)

在开始传统的复制(非 GTID 复制)前，需要完成以下几个关键点，**这几个关键点指导后续复制的所有步骤**。

1. 为 master 和 slave 设定不同的`server-id`，这是主从复制结构中非常关键的标识号。到了 MySQL 5.7，似乎不设置 server id 就无法开启 binlog。设置 server id 需要重启 MySQL 实例。
2. 开启 master 的 binlog。刚安装并初始化的 MySQL 默认未开启 binlog，建议手动设置 binlog 且为其设定文件名，否则默认以主机名为基名时修改主机名后会找不到日志文件。
3. 最好设置 master 上的变量`sync_binlog=1`(MySQL 5.7.7 之后默认为 1，之前的版本默认为 0)，这样每写一次二进制日志都将其刷新到磁盘，让 slave 服务器可以尽快地复制。防止万一 master 的二进制日志还在缓存中就宕机时，slave 无法复制这部分丢失的数据。
4. 最好设置 master 上的 redo log 的刷盘变量`innodb_flush_log_at_trx_commit=1`(默认值为 1)，这样每次提交事务都会立即将事务刷盘保证持久性和一致性。
5. 在 slave 上开启中继日志 relay log。这个是默认开启的，同样建议手动设置其文件名。
6. 建议在 master 上专门创建一个用于复制的用户，它只需要有复制权限`replication slave`用来读取 binlog。
7. 确保 slave 上的数据和 master 上的数据在"复制的起始 position 之前"是完全一致的。如果 master 和 slave 上数据不一致，复制会失败。
8. 记下 master 开始复制前 binlog 的 position，因为在 slave 连接 master 时需要指定从 master 的哪个 position 开始复制。
9. 考虑是否将 slave 设置为只读，也就是开启`read_only`选项。这种情况下，除了具有 super 权限(mysql 5.7.16 还提供了`super_read_only`禁止 super 的写操作)和 SQL 线程能写数据库，其他用户都不能进行写操作。这种禁写对于 slave 来说，绝大多数场景都非常适合。

## 4.1 一主一从

一主一从是最简单的主从复制结构。本节实验环境如下：

![img](../assets/733013-20180528194339716-360937433.png)

1. **配置 master 和 slave 的配置文件。**

```bash
[mysqld]          # master
datadir=data
socket=datamysql.sock
log-bin=master-bin
sync-binlog=1
server-id=100
[mysqld]       # slave
datadir=data
socket=datamysql.sock
relay-log=slave-bin
server-id=111
```

1. 重启 master 和 slave 上的 MySQL 实例。

    ```bash
    service mysqld restart
    ```

2. **在 master 上创建复制专用的用户。**

    ```bash
    create user 'repl'@'192.168.100.%' identified by 'P@ssword1!';
    grant REPLICATION SLAVE on *.* to 'repl'@'192.168.100.%';
    ```

3. **将 slave 恢复到 master 上指定的坐标。** 这是备份恢复的内容，此处用一个小节来简述操作过程。详细内容见[MySQL 备份和恢复(一)、(二)、(三)](https://www.cnblogs.com/f-ck-need-u/p/9013458.html)。

## 4.2 将 slave 恢复到 master 指定的坐标

对于复制而言，有几种情况：

- (1).待复制的 master 没有新增数据，例如新安装的 mysql 实例。这种情况下，可以跳过恢复这个过程。

- (2).待复制的 master 上已有数据。这时需要将这些已有数据也应用到 slave 上，并获取 master 上 binlog 当前的坐标。只有 slave 和 master 的数据能匹配上，slave 重放 relay log 时才不会出错。

第一种情况此处不赘述。第二种情况有几种方法，例如使用 mysqldump、冷备份、xtrabackup 等工具，这其中又需要考虑是 MyISAM 表还是 InnoDB 表。
在实验开始之前，首先在 master 上新增一些测试数据，以 innodb 和 myisam 的数值辅助表为例。

```sql
DROP DATABASE IF EXISTS backuptest;
CREATE DATABASE backuptest;
USE backuptest;

# 创建myisam类型的数值辅助表和插入数据的存储过程

CREATE TABLE num_isam (n INT NOT NULL PRIMARY KEY) ENGINE = MYISAM ;
DROP PROCEDURE IF EXISTS proc_num1;
DELIMITER $$
CREATE PROCEDURE proc_num1 (num INT)
BEGIN
DECLARE rn INT DEFAULT 1 ;
TRUNCATE TABLE backuptest.num_isam ;
INSERT INTO backuptest.num_isam VALUES(1) ;
dd: WHILE rn *2 < num DO
BEGIN
INSERT INTO backuptest.num_isam
SELECT rn + n FROM backuptest.num_isam;
SET rn = rn* 2 ;
END ;
END WHILE dd;
INSERT INTO backuptest.num_isam
SELECT n + rn
FROM backuptest.num_isam
WHERE n + rn <= num;
END ;
$$
DELIMITER ;

# 创建innodb类型的数值辅助表和插入数据的存储过程

CREATE TABLE num_innodb (n INT NOT NULL PRIMARY KEY) ENGINE = INNODB ;
DROP PROCEDURE IF EXISTS proc_num2;
DELIMITER $$
CREATE PROCEDURE proc_num2 (num INT)
BEGIN
DECLARE rn INT DEFAULT 1 ;
TRUNCATE TABLE backuptest.num_innodb ;
INSERT INTO backuptest.num_innodb VALUES(1) ;
dd: WHILE rn * 2 < num DO
BEGIN
INSERT INTO backuptest.num_innodb
SELECT rn + n FROM backuptest.num_innodb;
SET rn = rn * 2 ;
END ;
END WHILE dd;
INSERT INTO backuptest.num_innodb
SELECT n + rn
FROM backuptest.num_innodb
WHERE n + rn <= num ;
END ;
$$
DELIMITER ;

# 分别向两个数值辅助表中插入100W条数据

CALL proc_num1 (1000000) ;
CALL proc_num2 (1000000) ;
```

所谓数值辅助表是只有一列的表，且这个字段的值全是数值，从 1 开始增长。例如上面的是从 1 到 100W 的数值辅助表。

```sql
mysql> select * from backuptest.num_isam limit 10;
+----+
| n  |
+----+
|  1 |
|  2 |
|  3 |
|  4 |
|  5 |
|  6 |
|  7 |
|  8 |
|  9 |
| 10 |
+----+
```

### 4.2.1 获取 master binlog 的坐标

**如果 master 是全新的数据库实例，或者在此之前没有开启过 binlog，那么它的坐标位置是 position=4**。之所以是 4 而非 0，是因为 binlog 的前 4 个记录单元是每个 binlog 文件的头部信息。
如果 master 已有数据，或者说 master 以前就开启了 binlog 并写过数据库，那么需要手动获取 position。**为了安全以及没有后续写操作，必须先锁表。**

```bash
mysql> flush tables with read lock;
```

注意，这次的 **锁表会导致写阻塞以及 innodb 的 commit 操作。** 然后查看 binlog 的坐标。

```plaintext
mysql> show master status;   # 为了排版，简化了输出结果
+-------------------+----------+--------------+--------+--------+
| File              | Position | Binlog_Do_DB | ...... | ...... |
+-------------------+----------+--------------+--------+--------+
| master-bin.000001 |      623 |              |        |        |
+-------------------+----------+--------------+--------+--------+
```

记住 master-bin.000001 和 623。

### 4.2.2 备份 master 数据到 slave 上

下面给出 3 种备份方式以及对应 slave 的恢复方法。建议备份所有库到 slave 上，如果要筛选一部分数据库或表进行复制，应该在 slave 上筛选(筛选方式见后文[筛选要复制的库和表](https://www.cnblogs.com/f-ck-need-u/p/9155003.html#blog6.1))，而不应该在 master 的备份过程中指定。

**方式一：冷备份直接 cp。这种情况只适用于没有新写入操作。严谨一点，只适合拷贝完成前 master 不能有写入操作。**

1. 如果要复制所有库，那么直接拷贝整个 datadir。
2. 如果要复制的是某个或某几个库，直接拷贝相关目录即可。但注意，这种冷备份的方式只适合 MyISAM 表和开启了`innodb_file_per_table=ON`的 InnoDB 表。如果没有开启该变量，innodb 表使用公共表空间，无法直接冷备份。
3. 如果要冷备份 innodb 表，最安全的方法是先关闭 master 上的 mysql，而不是通过表锁。 所以，**如果没有涉及到 innodb 表，那么在锁表之后，可以直接冷拷贝。最后释放锁。**

```bash
   mysql> flush tables with read lock;
   mysql> show master status;   # 为了排版，简化了输出结果
   +-------------------+----------+--------------+--------+--------+
   | File              | Position | Binlog_Do_DB | ...... | ...... |
   +-------------------+----------+--------------+--------+--------+
   | master-bin.000001 |      623 |              |        |        |
   +-------------------+----------+--------------+--------+--------+
   shell> rsync -avz data 192.168.100.150:
   mysql> unlock tables;
```

此处实验，假设要备份的是整个实例，因为 **涉及到了 innodb 表，所以建议关闭 MySQL**。因为是冷备份，所以 slave 上也应该关闭 MySQL。

```bash
# master和slave上都执行
shell> mysqladmin -uroot -p shutdown
```

然后将整个 datadir 拷贝到 slave 上(当然，有些文件是不用拷贝的，比如 master 上的 binlog、mysql 库等)。

```bash
# 将master的datadir(data)拷贝到slave的datadir(data)
shell> rsync -avz data 192.168.100.150:
```

需要注意，在冷备份的时候，需要将备份到目标主机上的 DATADIRauto.conf 删除，这个文件中记录的是 mysql server 的 UUID，而 master 和 slave 的 UUID 必须不能一致。

然后重启 master 和 slave。因为重启了 master，所以 binlog 已经滚动了，不过这次不用再查看 binlog 坐标，因为重启造成的 binlog 日志移动不会影响 slave。

**方式二：使用 mysqldump 进行备份恢复。**

这种方式简单的多，而且对于 innodb 表很适用，但是 slave 上恢复时速度慢，因为恢复时数据全是通过 insert 插入的。因为 mysqldump 可以进行定时点恢复甚至记住 binlog 的坐标，所以无需再手动获取 binlog 的坐标。

```bash
shell> mysqldump -uroot -p --all-databases --master-data=2 >dump.db
```

注意，`--master-data`选项将再 dump.db 中加入`change master to`相关的语句，值为 2 时，`change master to`语句是注释掉的，值为 1 或者没有提供值时，这些语句是直接激活的。同时，`--master-data`会锁定所有表(如果同时使用了`--single-transaction`，则不是锁所有表，详细内容请参见[mysqldump](https://www.cnblogs.com/f-ck-need-u/p/9013458.html))。

因此，可以直接从 dump.db 中获取到 binlog 的坐标。**记住这个坐标。**

```bash
[root@xuexi ~]# grep -i -m 1 'change master to' dump.db 
-- CHANGE MASTER TO MASTER_LOG_FILE='master-bin.000002', MASTER_LOG_POS=154;
```

然后将 dump.db 拷贝到 slave 上，使用 mysql 执行 dump.db 脚本即可。也可以直接在 master 上远程连接到 slave 上执行。例如：

```bash
shell> mysql -uroot -p -h 192.168.100.150 -e 'source dump.db'
```

**方式三：使用 xtrabackup 进行备份恢复。**

这是三种方式中最佳的方式，安全性高、速度快。因为 xtrabackup 备份的时候会记录 master 的 binlog 的坐标，因此也无需手动获取 binlog 坐标。

xtrabackup 详细的备份方法见：[xtrabackup](https://www.cnblogs.com/f-ck-need-u/p/9018716.html)

注意：master 和 slave 上都安装 percona-xtrabackup。

以全备份为例：

```bash
innobackupex -u root -p backup
```

备份完成后，在 backup 下生成一个以时间为名称的目录。其内文件如下：

```bash
[root@xuexi ~]# ll backup2018-05-29_04-12-15
total 77872
-rw-r----- 1 root root      489 May 29 04:12 backup-my.cnf
drwxr-x--- 2 root root     4096 May 29 04:12 backuptest
-rw-r----- 1 root root     1560 May 29 04:12 ib_buffer_pool
-rw-r----- 1 root root 79691776 May 29 04:12 ibdata1
drwxr-x--- 2 root root     4096 May 29 04:12 mysql
drwxr-x--- 2 root root     4096 May 29 04:12 performance_schema
drwxr-x--- 2 root root    12288 May 29 04:12 sys
-rw-r----- 1 root root       22 May 29 04:12 xtrabackup_binlog_info
-rw-r----- 1 root root      115 May 29 04:12 xtrabackup_checkpoints
-rw-r----- 1 root root      461 May 29 04:12 xtrabackup_info
-rw-r----- 1 root root     2560 May 29 04:12 xtrabackup_logfile
```

其中 xtrabackup_binlog_info 中记录了 binlog 的坐标。**记住这个坐标。**

```bash
[root@xuexi ~]# cat backup2018-05-29_04-12-15xtrabackup_binlog_info 
master-bin.000002       154
```

然后将备份的数据执行"准备"阶段。这个阶段不要求连接 mysql，因此不用给连接选项。

```bash
innobackupex --apply-log backup2018-05-29_04-12-15
```

最后，将 backup 目录拷贝到 slave 上进行恢复。恢复的阶段就是向 MySQL 的 datadir 拷贝。但注意，xtrabackup 恢复阶段要求 datadir 必须为空目录。否则报错：

```bash
[root@xuexi ~]# innobackupex --copy-back backup2018-05-29_04-12-15
180529 23:54:27 innobackupex: Starting the copy-back operation
IMPORTANT: Please check that the copy-back run completes successfully.
At the end of a successful copy-back run innobackupex
prints "completed OK!".
innobackupex version 2.4.11 based on MySQL server 5.7.19 Linux (x86_64) (revision id: b4e0db5)
Original data directory data is not empty!
```

所以，停止 slave 的 mysql 并清空 datadir。

```bash
service mysqld stop
rm -rf data*
```

恢复时使用的模式是"--copy-back"，选项后指定要恢复的源备份目录。恢复时因为不需要连接数据库，所以不用指定连接选项。

```bash
[root@xuexi ~]# innobackupex --copy-back backup2018-05-29_04-12-15
180529 23:55:53 completed OK!
```

恢复完成后，MySQL 的 datadir 的文件的所有者和属组是 innobackupex 的调用者，所以需要改回 mysql.mysql。

```bash
shell> chown -R mysql.mysql data
```

启动 slave，并查看恢复是否成功。

```bash
shell> service mysqld start
shell> mysql -uroot -p -e 'select * from backuptest.num_isam limit 10;'
+----+
| n  |
+----+
|  1 |
|  2 |
|  3 |
|  4 |
|  5 |
|  6 |
|  7 |
|  8 |
|  9 |
| 10 |
+----+
```

## 4.3 slave 开启复制

经过前面的一番折腾，总算是把该准备的数据都准备到 slave 上，也获取到 master 上 binlog 的坐标(154)。现在还欠东风：连接 master。

连接 master 时，需要使用`change master to`提供连接到 master 的连接选项，包括 user、port、password、binlog、position 等。

```bash
mysql> change master to 
        master_host='192.168.100.20',
        master_port=3306,
        master_user='repl',
        master_password='P@ssword1!',
        master_log_file='master-bin.000002',
        master_log_pos=154;
```

完整的`change master to`语法如下：

```bash
CHANGE MASTER TO option [, option] ...
option:
  | MASTER_HOST = 'host_name'
  | MASTER_USER = 'user_name'
  | MASTER_PASSWORD = 'password'
  | MASTER_PORT = port_num
  | MASTER_LOG_FILE = 'master_log_name'
  | MASTER_LOG_POS = master_log_pos
  | MASTER_AUTO_POSITION = {0|1}
  | RELAY_LOG_FILE = 'relay_log_name'
  | RELAY_LOG_POS = relay_log_pos
  | MASTER_SSL = {0|1}
  | MASTER_SSL_CA = 'ca_file_name'
  | MASTER_SSL_CAPATH = 'ca_directory_name'
  | MASTER_SSL_CERT = 'cert_file_name'
  | MASTER_SSL_CRL = 'crl_file_name'
  | MASTER_SSL_CRLPATH = 'crl_directory_name'
  | MASTER_SSL_KEY = 'key_file_name'
  | MASTER_SSL_CIPHER = 'cipher_list'
  | MASTER_SSL_VERIFY_SERVER_CERT = {0|1}
```

然后，启动 IO 线程和 SQL 线程。可以一次性启动两个，也可以分开启动。

```bash
# 一次性启动、关闭
start slave;
stop slave;

# 单独启动
start slave io_thread;
start slave sql_thread;
```

至此，复制就已经可以开始工作了。当 master 写入数据，slave 就会从 master 处进行复制。

例如，在 master 上新建一个表，然后去 slave 上查看是否有该表。因为是 DDL 语句，它会写二进制日志，所以它也会复制到 slave 上。

## 4.4 查看 slave 的信息

`change master to`后，在 slave 的 datadir 下就会生成 master.info 文件和 relay-log.info 文件，这两个文件随着复制的进行，其内数据会随之更新。

### 4.4.1 master.info

master.info 文件记录的是 **IO 线程相关的信息**，也就是连接 master 以及读取 master binlog 的信息。通过这个文件，下次连接 master 时就不需要再提供连接选项。

以下是 master.info 的内容，每一行的意义见[官方手册](https://dev.mysql.com/doc/refman/5.7/en/slave-logs-status.html)

```bash
[root@xuexi ~]# cat datamaster.info 
25                        # 本文件的行数
master-bin.000002         # IO线程正从哪个master binlog读取日志
154                       # IO线程读取到master binlog的位置
192.168.100.20            # master_host
repl                      # master_user
P@ssword1!                # master_password
3306                      # master_port
60                        # master_retry，slave重连master的超时时间(单位秒)
0
0
30.000
0
86400
0
```

### 4.4.2 relay-log.info

relay-log.info 文件中记录的是 **SQL 线程相关的信息**。以下是 relay-log.info 文件的内容，每一行的意义见[官方手册](https://dev.mysql.com/doc/refman/5.7/en/slave-logs-status.html)

```bash
[root@xuexi ~]# cat datarelay-log.info 
7                   # 本文件的行数
.slave-bin.000001  # 当前SQL线程正在读取的relay-log文件
4                   # SQL线程已执行到的relay log位置
master-bin.000002   # SQL线程最近执行的操作对应的是哪个master binlog
154                 # SQL线程最近执行的操作对应的是master binlog的哪个位置
0                   # slave上必须落后于master多长时间
0                   # 正在运行的SQL线程数
1                   # 一种用于内部信息交流的ID，目前值总是1
```

### 4.4.3 show slave status

在 slave 上执行`show slave status`可以查看 slave 的状态信息。信息非常多，每个字段的详细意义可参见[官方手册](https://dev.mysql.com/doc/refman/5.7/en/show-slave-status.html)

```bash
mysql> show slave statusG
*************************** 1. row ***************************
               Slave_IO_State:        # slave上IO线程的状态，来源于show processlist
                  Master_Host: 192.168.100.20
                  Master_User: repl
                  Master_Port: 3306
                Connect_Retry: 60
              Master_Log_File: master-bin.000002
          Read_Master_Log_Pos: 154
               Relay_Log_File: slave-bin.000001
                Relay_Log_Pos: 4
        Relay_Master_Log_File: master-bin.000002
             Slave_IO_Running: No          # IO线程的状态，此处为未运行且未连接状态
            Slave_SQL_Running: No          # SQL线程的状态，此处为未运行状态
              Replicate_Do_DB:             # 显式指定要复制的数据库
          Replicate_Ignore_DB:             # 显式指定要忽略的数据库
           Replicate_Do_Table: 
       Replicate_Ignore_Table: 
      Replicate_Wild_Do_Table:          # 以通配符方式指定要复制的表
  Replicate_Wild_Ignore_Table: 
                   Last_Errno: 0
                   Last_Error: 
                 Skip_Counter: 0
          Exec_Master_Log_Pos: 154
              Relay_Log_Space: 154
              Until_Condition: None     # start slave语句中指定的until条件，
                                        # 例如，读取到哪个binlog位置就停止
               Until_Log_File: 
                Until_Log_Pos: 0
           Master_SSL_Allowed: No
           Master_SSL_CA_File: 
           Master_SSL_CA_Path: 
              Master_SSL_Cert: 
            Master_SSL_Cipher: 
               Master_SSL_Key: 
        Seconds_Behind_Master: NULL    # SQL线程执行过的位置比IO线程慢多少
Master_SSL_Verify_Server_Cert: No
                Last_IO_Errno: 0
                Last_IO_Error: 
               Last_SQL_Errno: 0
               Last_SQL_Error: 
  Replicate_Ignore_Server_Ids: 
             Master_Server_Id: 0      # master的server id
                  Master_UUID: 
             Master_Info_File: datamaster.info
                    SQL_Delay: 0
          SQL_Remaining_Delay: NULL
      Slave_SQL_Running_State:             # slave SQL线程的状态
           Master_Retry_Count: 86400
                  Master_Bind: 
      Last_IO_Error_Timestamp: 
     Last_SQL_Error_Timestamp: 
               Master_SSL_Crl: 
           Master_SSL_Crlpath: 
           Retrieved_Gtid_Set: 
            Executed_Gtid_Set: 
                Auto_Position: 0
         Replicate_Rewrite_DB: 
                 Channel_Name: 
           Master_TLS_Version: 
1 row in set (0.01 sec)
```

因为太长，后面再列出`show slave status`时，将裁剪一些意义不大的行。

再次回到上面`show slave status`的信息。除了那些描述 IO 线程、SQL 线程状态的行，还有几个 log_file 和 pos 相关的行，如下所列。

```bash
      Master_Log_File: master-bin.000002
  Read_Master_Log_Pos: 154
       Relay_Log_File: slave-bin.000001
        Relay_Log_Pos: 4
Relay_Master_Log_File: master-bin.000002
  Exec_Master_Log_Pos: 154
```

理解这几行的意义至关重要，前面因为排版限制，描述看上去有些重复。所以这里完整地描述它们：

- `Master_Log_File`：IO 线程正在读取的 master binlog；
- `Read_Master_Log_Pos`：IO 线程已经读取到 master binlog 的哪个位置；
- `Relay_Log_File`：SQL 线程正在读取和执行的 relay log；
- `Relay_Log_Pos`：SQL 线程已经读取和执行到 relay log 的哪个位置；
- `Relay_Master_Log_File`：SQL 线程最近执行的操作对应的是哪个 master binlog；
- `Exec_Master_Log_Pos`：SQL 线程最近执行的操作对应的是 master binlog 的哪个位置。

所以，(Relay_Master_Log_File, Exec_Master_log_Pos)构成一个坐标，这个坐标表示 slave 上已经将 master 上的哪些数据重放到自己的实例中，它可以用于下一次`change master to`时指定的 binlog 坐标。

与这个坐标相对应的是 slave 上 SQL 线程的 relay log 坐标(Relay_Log_File, Relay_Log_Pos)。这两个坐标位置不同，但它们对应的数据是一致的。

最后还有一个延迟参数`Seconds_Behind_Master`需要说明一下，它的本质意义是 SQL 线程比 IO 线程慢多少。如果 master 和 slave 之间的网络状况优良，那么 slave 的 IO 线程读速度和 master 写 binlog 的速度基本一致，所以这个参数也用来描述"SQL 线程比 master 慢多少"，也就是说 slave 比 master 少多少数据，只不过衡量的单位是秒。但需要注意，这个参数的描述并不标准，只有在网速很好的时候做个大概估计，很多种情况下它的值都是 0，即使 SQL 线程比 IO 线程慢了很多也是如此。

### 4.4.4 slave 信息汇总

上面的 master.info、relay-log.info 和`show slave status`的状态都是刚连接上 master 还未启动 IO thread、SQL thread 时的状态。下面将显示已经进行一段正在执行复制的 slave 状态。

首先查看启动 io thread 和 sql thread 后的状态。使用`show processlist`查看即可。

```bash
mysql> start slave;
mysql> show processlist;   # slave上的信息，为了排版，简化了输出
+----+-------------+---------+--------------------------------------------------------+
| Id | User        | Command | State                                                  |
+----+-------------+---------+--------------------------------------------------------+
|  4 | root        | Sleep   |                                                        |
|  7 | root        | Query   | starting                                               |
|  8 | system user | Connect | Waiting for master to send event                       |
|  9 | system user | Connect | Slave has read all relay log; waiting for more updates |
+----+-------------+---------+--------------------------------------------------------+
```

可以看到：
- `Id=8`的线程负责连接 master 并读取 binlog，它是 IO 线程，它的状态指示"等待 master 发送更多的事件"；
- `Id=9`的线程负责读取 relay log，它是 SQL 线程，它的状态指示"已经读取了所有的 relay log"。

再看看此时 master 上的信息。

```bash
mysql> show processlist;        # master上的信息，为了排版，经过了修改
+----+------+-----------------------+-------------+--------------------------------------+
| Id | User | Host                  | Command     | State                                |
+----+------+-----------------------+-------------+--------------------------------------+
| 4  | root | localhost             | Query       | starting                             |
|----| ---- | --------------------- | ----------- | ------------------------------------ |
| 16 | repl | 192.168.100.150:39556 | Binlog Dump | Master has sent all binlog to slave; |
|    |      |                       |             | waiting for more updates             |
+----+------+-----------------------+-------------+--------------------------------------+
```

master 上有一个`Id=16`的 binlog dump 线程，该线程的用户是 repl。它的状态指示"已经将所有的 binlog 发送给 slave 了"。

现在，在 master 上执行一个长事件，以便查看 slave 上的状态信息。

仍然使用前面插入数值辅助表的存储过程，这次分别向两张表中插入一亿条数据(尽管去抽烟、喝茶，够等几分钟的。如果机器性能不好，请大幅减少插入的行数)。

```bash
call proc_num1(100000000);
call proc_num2(100000000);
```

然后去 slave 上查看信息，如下。因为太长，已经裁剪了一部分没什么用的行。

```bash
mysql> show slave status\G
mysql: [Warning] Using a password on the command line interface can be insecure.
*************************** 1. row ***************************
               Slave_IO_State: Waiting for master to send event
                  Master_Host: 192.168.100.20
                  Master_User: repl
                  Master_Port: 3306
                Connect_Retry: 60
              Master_Log_File: master-bin.000003
          Read_Master_Log_Pos: 512685413
               Relay_Log_File: slave-bin.000003
                Relay_Log_Pos: 336989434
        Relay_Master_Log_File: master-bin.000003
             Slave_IO_Running: Yes
            Slave_SQL_Running: Yes
          Exec_Master_Log_Pos: 336989219
      Slave_SQL_Running_State: Reading event from the relay log
```

从中获取到的信息有：

1. IO 线程的状态
2. SQL 线程的状态
3. IO 线程读取到 master binlog 的哪个位置：512685413
4. SQL 线程已经执行到 relay log 的哪个位置：336989434
5. SQL 线程执行的位置对应于 master binlog 的哪个位置：336989219

可以看出，IO 线程比 SQL 线程超前了很多很多，所以 SQL 线程比 IO 线程的延迟较大。

## 4.5 MySQL 复制如何实现断开重连

很多人以为`change master to`语句是用来连接 master 的，实际上这种说法是错的。连接 master 是 IO 线程的事情，`change master to`只是为 IO 线程连接 master 时提供连接参数。

如果 slave 从来没连接过 master，那么必须使用`change master to`语句来生成 IO 线程所需要的信息，这些信息记录在 master.info 中。这个文件是`change master to`成功之后立即生成的，以后启动 IO 线程时，IO 线程都会自动读取这个文件来连接 master，不需要先执行`change master to`语句。

例如，可以随时`stop slave`来停止复制线程，然后再随时`start slave`，只要 master.info 存在，且没有人为修改过它，IO 线程就一定不会出错。这是因为 master.info 会随着 IO 线程的执行而更新，无论读取到 master binlog 的哪个位置，都会记录下这个位置，如此一来，IO 线程下次启动的时候就知道从哪里开始监控 master binlog。

前面还提到一个文件：`relay-log.info`文件。这个文件中记录的是 SQL 线程的相关信息，包括读取、执行到 relay log 的哪个位置，刚重放的数据对应 master binlog 的哪个位置。随着复制的进行，这个文件的信息会即时改变。所以，通过 relay-log.info，下次 SQL 线程启动的时候就能知道从 relay log 的哪个地方继续读取、执行。

如果不小心把 relay log 文件删除了，SQL 线程可能会丢失了一部分相比 IO 线程延迟的数据。这时候，只需将 relay-log.info 中第 4、5 行记录的"SQL 线程刚重放的数据对应 master binlog 的坐标"手动修改到 master.info 中即可，这样 IO 线程下次连接 master 就会从 master binlog 的这个地方开始监控。当然，也可以将这个坐标作为`change master to`的坐标来修改 master.info。

此外，当 mysql 实例启动时，默认会自动`start slave`，也就是 MySQL 一启动就自动开启复制线程。如果想要禁止这种行为，在配置文件中加上：

```
[mysqld]
skip-slave-start
```

## 4.6 一些变量

默认情况下，slave 连接到 master 后会在 slave 的 datadir 下生成 master.info 和 relay-log.info 文件，但是这是可以通过设置变量来改变的。

- `master-info-repository={TABLE|FILE}`：master 的信息是记录到文件 master.info 中还是记录到表 mysql.slave_master_info 中。默认为 file。
- `relay-log-info-repository={TABLE|FILE}`：slave 的信息是记录到文件 relay-log.info 中还是记录到表 mysql.slave_relay_log_info 中。默认为 file。

IO 线程每次从 master 复制日志要写入到 relay log 中，但是它是先放在内存的，等到一定时机后才会将其刷到磁盘上的 relay log 文件中。刷到磁盘的时机可以由变量控制。

另外，IO 线程每次从 master 复制日志后都会更新 master.info 的信息，也是先更新内存中信息，在特定的时候才会刷到磁盘的 master.info 文件；同理 SQL 线程更新 realy-log.info 也是一样的。它们是可以通过变量来设置更新时机的。

- `sync-relay-log=N`：设置为大于 0 的数表示每从 master 复制 N 个事件就刷一次盘。设置为 0 表示依赖于操作系统的 sync 机制。
- `sync-master-info=N`：依赖于`master-info-repository`的设置，如果为 file，则设置为大于 0 的值时表示每更新多少次 master.info 将其写入到磁盘的 master.info 中，设置为 0 则表示由操作系统来决定何时调用`fdatasync()`函数刷到磁盘。如果设置为 table，则设置为大于 0 的值表示每更新多少次 master.info 就更新 mysql.slave_master_info 表一次，如果设置为 0 则表示永不更新该表。
- `sync-relay-log-info=N`：同上。

# 5.一主多从

一主多从有两种情况，结构图如下。

以下是一主多从的结构图(和一主一从的配置方法完全一致)：

![img](../assets/733013-20180528163904784-673253663.png)

以下是一主多从，但某 slave 是另一群 MySQL 实例的 master：

![img](../assets/733013-20180528163917913-780164983.png)

配置一主多从时，需要考虑一件事：slave 上是否要开启 binlog? 如果不开启 slave 的 binlog，性能肯定要稍微好一点。但是开启了 binlog 后，可以通过 slave 来备份数据，也可以在 master 宕机时直接将 slave 切换为新的 master。此外，如果是上面第二种主从结构，这台 slave 必须开启 binlog。可以将某台或某几台 slave 开启 binlog，并在 mysql 动静分离的路由算法上稍微减少一点到这些 slave 上的访问权重。

上面第一种一主多从的结构没什么可解释的，它和一主一从的配置方式完全一样，但是可以考虑另一种情况：向现有主从结构中添加新的 slave。所以，稍后先介绍这种添加 slave，再介绍第二种一主多从的结构。

## 5.1 向现有主从结构中添加 slave

官方手册：[https://dev.mysql.com/doc/refman/5.7/en/replication-howto-additionalslaves.html](https://dev.mysql.com/doc/refman/5.7/en/replication-howto-additionalslaves.html)

例如在前文一主一从的实验环境下添加一台新的 slave。

因为新的 slave 在开始复制前，要有 master 上的基准数据，还要有 master binlog 的坐标。按照前文一主一从的配置方式，当然很容易获取这些信息，但这样会将 master 锁住一段时间(因为要备份基准数据)。

深入思考一下，其实 slave 上也有数据，还有 relay log 以及一些仓库文件标记着数据复制到哪个地方。所以，完全 **可以从 slave 上获取基准数据和坐标，也建议这样做**。

仍然有三种方法从 slave 上获取基准数据：冷备份、mysqldump 和 xtrabackup。方法见前文[将 slave 恢复到 master 指定的坐标](https://www.cnblogs.com/f-ck-need-u/p/9155003.html#blog4.2)。

其实 **临时关闭一个 slave 对业务影响很小，所以我个人建议，新添加 slave 时采用冷备份 slave 的方式**，不仅备份恢复的速度最快，配置成 slave 也最方便，这一点和前面配置"一主一从"不一样。但冷备份 slave 的时候需要注意几点：

1. 可以考虑将 slave1 完全 shutdown 再将整个 datadir 拷贝到新的 slave2 上。
2. **建议新的 slave2 配置文件中的"relay-log"的值和 slave1 的值完全一致**，否则应该手动从 slave2 的 relay-log.info 中获取 IO 线程连接 master 时的坐标，并在 slave2 上使用`change master to`语句设置连接参数。 方法很简单，所以不做演示了。

## 5.2 配置一主多从(从中有从)

此处实现的一主多从是下面这种结构：

![img](../assets/733013-20180528163917913-780164983.png)

这种结构对 MySQL 复制来说，是一个很好的提升性能的方式。对于只有一个 master 的主从复制结构，每多一个 slave，意味着 master 多发一部分 binlog，业务稍微繁忙一点时，这种压力会加剧。而这种一个主 master、一个或多个辅助 master 的主从结构，非常有助于 MySQL 集群的伸缩性，对压力的适应性也很强。

> 除上面一主多从、从中有从的方式可提升复制性能，还有几种提升 MySQL 复制性能的方式：
    1.  将不同数据库复制到不同 slave 上。
    2.  可以将 master 上的事务表(如 InnoDB)复制为 slave 上的非事务表(如 MyISAM)，这样 slave 上回放的速度加快，查询数据的速度在一定程度上也会提升。

回到这种主从结构，它有些不同，master 只负责传送日志给 slave1、slave2 和 slave3，slave 2_1 和 slave 2_2 的日志由 slave2 负责传送，所以 slave2 上也必须要开启 binlog 选项。此外，还必须开启一个选项`--log-slave-updates`让 slave2 能够在重放 relay log 时也写自己的 binlog，否则 slave2 的 binlog 仅接受人为的写操作。**问：slave 能否进行写操作？重放 relay log 的操作是否会记录到 slave 的 binlog 中？** 1.  在 slave 上没有开启`read-only`选项(只读变量)时，任何有写权限的用户都可以进行写操作，这些操作都会记录到 binlog 中。注意，**read-only 选项对具有 super 权限的用户以及 SQL 线程执行的重放写操作无效**。默认这个选项是关闭的。

```
mysql> show variables like "read_only"; 
+---------------+-------+
| Variable_name | Value |
+---------------+-------+
| read_only     | OFF   |
+---------------+-------+
```

1. 在 slave 上没有开启`log-slave-updates`和 binlog 选项时，重放 relay log 不会记录 binlog。**所以如果 slave2 要作为某些 slave 的 master，那么在 slave2 上必须要开启 log-slave-updates 和 binlog 选项。为了安全和数据一致性，在 slave2 上还应该启用 read-only 选项。** 环境如下：

![img](../assets/733013-20180608100823680-1104661841.png)

以下是 master、slave1 和 slave2 上配置文件内容。

```
# master上的配置
[mysqld]
datadir=/data
socket=/data/mysql.sock
server_id=100
sync-binlog=1
log_bin=master-bin
log-error=/data/err.log
pid-file=/data/mysqld.pid

# slave1上的配置
[mysqld]
datadir=/data
socket=/data/mysql.sock
server_id=111
relay-log=slave-bin
log-error=/data/err.log
pid-file=/data/mysqld.pid

log-slave-updates          # 新增配置
log-bin=master-slave-bin   # 新增配置
read-only=ON               # 新增配置

# slave2上的配置
[mysqld]
datadir=/data
socket=/data/mysql.sock
server_id=123
relay-log=slave-bin
log-error=/data/err.log
pid-file=/data/mysqld.pid
read-only=ON
```

因为 slave2 目前是全新的实例，所以先将 slave1 的基准数据备份到 slave2。由于 slave1 自身就是 slave，临时关闭一个 slave 对业务影响很小，所以直接采用冷备份 slave 的方式。

```bash
# 在slave2上执行
shell> mysqladmin -uroot -p shutdown

# 在slave1上执行：
shell> mysqladmin -uroot -p shutdown
shell> rsync -az --delete /data 192.168.100.19:/
shell> service mysqld start
```

**冷备份时，以下几点千万注意** ：

1. 因为 slave2 是 slave1 的从，所以在启动 MySQL 前必须将备份到 slave2 上的和复制有关的文件都删除 。包括：
    - (1).master.info。除非配置文件中指定了`skip-slave-start`，否则 slave2 将再次连接到 master 并作为 master 的 slave。
    - (2).relay-log.info。因为 slave1 启动后会继续执行 relay log 中的内容(如果有未执行的)，这时 slave1 会将这部分写入 binlog 并传送到 slave2。
    - (3).删除 relay log 文件。其实不是必须删除，但建议删除。
    - (4).删除 relay log index 文件。
    - (5).删除 DATADIR/auto.conf。这个文件必须删除，因为这里面保留了 mysql server 的 UUID，而 master 和 slave 的 UUID 必须不能一致。在启动 mysql 的时候，如果没有这个文件会自动生成自己的 UUID 并保存到 auto.conf 中。

2. 检查 slave1 上从 master 复制过来的专门用于复制的用户`repl`是否允许 slave2 连接。如果不允许，应该去 master 上修改这个用户。

3. 因为 slave1 是刚开启的 binlog，所以 slave2 连接 slave1 时的 binlog position 应该指定为 4。即使 slave1 不是刚开启的 binlog，它在重启后也会滚动 binlog。

所以，在 slave2 上继续操作：

```bash
hell> ls /data
auto.cnf    ib_buffer_pool  ib_logfile1  performance_schema  slave-bin.000005
backuptest  ibdata1         master.info  relay-log.info      slave-bin.index
err.log     ib_logfile0     mysql        slave-bin.000004    sys            

shell> rm -f /data/{master.info,relay-log.info,auto.conf,slave-bin*}
shell> service mysqld start
```

最后连上 slave2，启动复制线程。

```bash
shell> mysql -uroot -p
mysql> change master to
        master_host='192.168.100.150',
        master_port=3306,
        master_user='repl',
        master_password='P@ssword1!',
        master_log_file='master-slave-bin.000001',
        master_log_pos=4;
mysql> start slave;
mysql> show slave status\G
```

# 6.MySQL 复制中一些常用操作

## 6.1 筛选要复制的库和表

默认情况下，slave 会复制 master 上所有库。可以指定以下变量显式指定要复制的库、表和要忽略的库、表，也可以将其写入配置文件。

```bash
Replicate_Do_DB: 要复制的数据库
        Replicate_Ignore_DB: 不复制的数据库
         Replicate_Do_Table: 要复制的表
     Replicate_Ignore_Table: 不复制的表
    Replicate_Wild_Do_Table: 通配符方式指定要复制的表
Replicate_Wild_Ignore_Table: 通配符方式指定不复制的表
```

如果要指定列表，则多次使用这些变量进行设置。

需要注意的是，**尽管显式指定了要复制和忽略的库或者表，但是 master 还是会将所有的 binlog 传给 slave 并写入到 slave 的 relay log 中，真正负责筛选的 slave 上的 SQL 线程**。

另外，如果 slave 上开启了 binlog，SQL 线程读取 relay log 后会将所有的事件都写入到自己的 binlog 中，只不过对于那些被忽略的事件只记录相关的事务号等信息，不记录事务的具体内容。所以，如果之前设置了被忽略的库或表，后来取消忽略后，它们在取消忽略以前的变化是不会再重放的，特别是基于 gtid 的复制会严格比较 binlog 中的 gtid。

总之使用筛选的时候应该多多考虑是否真的要筛选，是否是永久筛选。

## 6.2 reset slave 和 reset master

`reset slave`会删除 master.info/relay-log.info 和 relay log，然后新生成一个 relay log。但是`change master to`设置的连接参数还在内存中保留着，所以此时可以直接 start slave，并根据内存中的`change master to`连接参数复制日志。

`reset slave all`除了删除`reset slave`删除的东西，还删除内存中的`change master to`设置的连接信息。

`reset master`会删除 master 上所有的二进制日志，并新建一个日志。在正常运行的主从复制环境中，执行`reset master`很可能导致异常状况。所以建议使用 purge 来删除某个时间点之前的日志(应该保证只删除那些已经复制完成的日志)。

## 6.3 show slave hosts

如果想查看 master 有几个 slave 的信息，可以使用`show slave hosts`。以下为某个 master 上的结果：

```bash
mysql> show slave hosts; 
+-----------+------+------+-----------+--------------------------------------+
| Server_id | Host | Port | Master_id | Slave_UUID                           |
+-----------+------+------+-----------+--------------------------------------+
|       111 |      | 3306 |        11 | ff7bb057-2466-11e7-8591-000c29479b32 |
|      1111 |      | 3306 |        11 | 9b119463-24d2-11e7-884e-000c29867ec2 |
+-----------+------+------+-----------+--------------------------------------+
```

可以看到，该 show 中会显示 server-id、slave 的主机地址和端口号、它们的 master_id 以及这些 slave 独一无二的 uuid 号。

其中 show 结果中的 host 显示结果是由 slave 上的变量 report_host 控制的，端口是由 report_port 控制的。

例如，在 slave2 上修改其配置文件，添加 report-host 项后重启 MySQL 服务。

```bash
[mysqld]
report_host=192.168.100.19
```

在 slave1(前文的实验环境，slave1 是 slave2 的 master)上查看，host 已经显示为新配置的项。

```bash
mysql> show slave hosts;
+-----------+----------------+------+-----------+--------------------------------------+
| Server_id | Host           | Port | Master_id | Slave_UUID                           |
+-----------+----------------+------+-----------+--------------------------------------+
|       111 | 192.168.100.19 | 3306 |        11 | ff7bb057-2466-11e7-8591-000c29479b32 |
|      1111 |                | 3306 |        11 | 9b119463-24d2-11e7-884e-000c29867ec2 |
+-----------+----------------+------+-----------+--------------------------------------+
```

## 6.4 多线程复制

在老版本中，只有一个 SQL 线程读取 relay log 并重放。重放的速度肯定比 IO 线程写 relay log 的速度慢非常多，导致 SQL 线程非常繁忙，且 **实现到从库上延迟较大**。**没错，多线程复制可以解决主从延迟问题，且使用得当的话效果非常的好(关于主从复制延迟，是生产环境下最常见的问题之一，且没有很好的办法来避免。后文稍微介绍了一点方法)**。

在 MySQL 5.6 中引入了多线程复制(multi-thread slave，简称 MTS)，这个 **多线程指的是多个 SQL 线程，IO 线程还是只有一个**。当 IO 线程将 master binlog 写入 relay log 中后，一个称为"多线程协调器(multithreaded slave coordinator)"会对多个 SQL 线程进行调度，让它们按照一定的规则去执行 relay log 中的事件。

**需要谨记于心的是，如果对多线程复制没有了解的很透彻，千万不要在生产环境中使用多线程复制。** 它的确带来了一些复制性能的提升，并且能解决主从超高延迟的问题，但随之而来的是很多的"疑难杂症"，这些"疑难杂症"并非是 bug，只是需要多多了解之后才知道为何会出现这些问题以及如何解决这些问题。稍后会简单介绍一种多线程复制问题：gaps。

通过全局变量`slave-parallel-workers`控制 SQL 线程个数，设置为非 0 正整数 N，表示多加 N 个 SQL 线程，加上原有的共 N+1 个 SQL 线程。默认为 0，表示不加任何 SQL 线程，即关闭多线程功能。

```bash
mysql> show variables like "%parallel%";
+------------------------+-------+
| Variable_name          | Value |
+------------------------+-------+
| slave_parallel_workers | 0     |
+------------------------+-------+
```

显然，多线程只有在 slave 上开启才有效，因为只有 slave 上才有 SQL 线程。另外，设置了该全局变量，需要 **重启 SQL 线程** 才生效，否则内存中还是只有一个 SQL 线程。

例如，初始时 slave 上的 processlist 如下：

![img](../assets/733013-20180606081617238-1542051622.png)

设置`slave_parallel_workers=2`。

```bash
mysql> set @@global.slave_parallel_workers=2;
mysql> stop slave sql_thread;
msyql> start slave sql_thread;
mysql> show full processlist;
```

![img](../assets/733013-20180606081705265-1189641192.png)

可见多出了两个线程，其状态信息是"Waiting for an event from Coordinator"。

虽然是多个 SQL 线程，但是复制时每个库只能使用一个线程(默认情况下，可以通过`--slave-parallel-type`修改并行策略)，因为如果一个库可以使用多个线程，多个线程并行重放 relay log，可能导致数据错乱。所以应该设置线程数等于或小于要复制的库的数量，设置多了无效且浪费资源。

### 6.4.1 多线程复制带来的不一致问题

虽然多线程复制带来了一定的复制性能提升，但它也带来了很多问题，最严重的是一致性问题。完整的内容见[官方手册](https://dev.mysql.com/doc/refman/8.0/en/replication-features-transaction-inconsistencies.html)。此处介绍其中一个最重要的问题。

**关于多线程复制，最常见也是开启多线程复制前最需要深入了解的问题是：由于多个 SQL 线程同时执行 relay log 中的事务，这使得 slave 上提交事务的顺序很可能和 master binlog 中记录的顺序不一致(除非指定变量 slave_preserve_commit_order=1)。** (注意：这里说的是事务而不是事件。因为 MyISAM 的 binlog 顺序无所谓，只要执行完了就正确，而且多线程协调器能够协调好这些任务。所以只需考虑 innodb 基于事务的 binlog)

举个简单的例子，master 上事务 A 先于事务 B 提交，到了 slave 上因为多 SQL 线程的原因，可能事务 B 提交了事务 A 却还没提交。

是否还记得`show slave status`中的`Exec_master_log_pos`代表的意义？它表示 SQL 线程最近执行的事件对应的是 master binlog 中的哪个位置。问题由此而来。通过`show slave status`，我们看到已经执行事件对应的坐标，它前面可能还有事务没有执行。而在 relay log 中，事务 B 记录的位置是在事务 A 之后的(和 master 一样)，于是事务 A 和事务 B 之间可能就存在一个孔洞(gap)，这个孔洞是事务 A 剩余要执行的操作。

正常情况下，多线程协调器记录了一切和多线程复制相关的内容，它能识别这种孔洞(通过打低水位标记 low-watermark)，也能正确填充孔洞。**即使是在存在孔洞的情况下执行 stop slave 也不会有任何问题，因为在停止 SQL 线程之前，它会等待先把孔洞填充完**。但危险因素太多，比如突然宕机、突然杀掉 mysqld 进程等等，这些都会导致孔洞持续下去，甚至可能因为操作不当而永久丢失这部分孔洞。

那么如何避免这种问题，出现这种问题如何解决？

**1.如何避免 gap。**

前面说了，多个 SQL 线程是通过协调器来调度的。默认情况下，可能会出现 gap 的情况，这是因为变量`slave_preserve_commit_order`的默认值为 0。该变量指示协调器是否让每个 SQL 线程执行的事务按 master binlog 中的顺序提交。因此，将其设置为 1，然后重启 SQL 线程即可保证 SQL 线程按序提交，也就不可能会有 gap 的出现。

当事务 B 准备先于事务 A 提交的时候，它将一直等待。此时 slave 的状态将显示：

```bash
1 Waiting for preceding transaction to commit   # MySQL 5.7.8之后显示该状态
2 Waiting for its turn to commit       # MySQL 5.7.8之前显示该状态
```

尽管不会出现 gap，但`show slave status`的`Exec_master_log_pos`仍可能显示在事务 A 的坐标之后。

由于开启`slave_preserve_commit_order`涉及到不少操作，它还要求开启 slave 的 binlog`--log-bin`(因此需要重启 mysqld)，且开启重放 relay log 也记录 binlog 的行为`--log-slave-updates`，此外，还必须设置多线程的并行策略`--slave-parallel-type=LOGICAL_CLOCK`。

```bash
shell> mysqladmin -uroot -p shutdown
shell> cat /etc/my.cnf
log_bin=slave-bin
log-slave-updates
slave_parallel_workers=1
slave_parallel_type=LOGICAL_CLOCK
shell>service mysqld start
```

**2.如何处理已经存在的 gap。**

方法之一，是从 master 上重新备份恢复到 slave 上，这种方法是处理不当的最后解决办法。

正常的处理方法是，使用`START SLAVE [SQL_THREAD] UNTIL SQL_AFTER_MTS_GAPS;`，它表示 SQL 线程只有先填充 gaps 后才能启动。实际上，它涉及了两个操作：

- (1).填充 gaps
- (2).自动停止 SQL 线程(所以之后需要手动启动 SQL 线程)

一般来说，在填充完 gaps 之后，应该先`reset slave`移除已经执行完的 relay log，然后再去启动 sql_thread。

### 6.4.2 多线程复制切换回单线程复制

多线程的带来的问题不止 gaps 一种，所以没有深入了解多线程的情况下，千万不能在生产环境中启用它。如果想将多线程切换回单线程，可以执行如下操作：

```bash
START SLAVE UNTIL SQL_AFTER_MTS_GAPS;
SET @@GLOBAL.slave_parallel_workers = 0;
START SLAVE SQL_THREAD;
```

## 6.5 slave 升级为 master 的大致操作

当 master 突然宕机，有时候需要切换到 slave，将 slave 提升为新的 master。但对于 master 突然宕机可能造成的数据丢失，主从切换是无法解决的，它只是尽可能地不间断提供 MySQL 服务。

假如现在有主服务器 M，从服务器 S1、S2，S1 作为将来的新的 master。

1. 在将 S1 提升为 master 之前，需要保证 S1 已经将 relay log 中的事件已经 replay 完成。即下面两个状态查看语句中 SQL 线程的状态显示为："Slave has read all relay log; waiting for the slave I/O thread to update it"。

    ```bash
    show slave status;
    show processlist;
    ```

2. 停止 S1 上的 IO 线程和 SQL 线程，然后将 S1 的 binlog 清空(要求已启用 binlog)。

    ```bash
    mysql> stop slave;
    mysql> reset master;
    ```

3. 在 S2 上停止 IO 线程和 SQL 线程，通过`change master to`修改 master 的指向为 S1，然后再启动 io 线程和 SQL 线程。

    ```bash
    mysql> stop slave;
    mysql> change master to master_host=S1,...
    mysql> start slave;
    ```

4. 将应用程序原本指向 M 的请求修改为指向 S1，如修改 MySQL 代理的目标地址。一般会通过 MySQL Router、Amoeba、cobar 等数据库中间件来实现。
5. 删除 S1 上的 master.info、relay-log.info 文件，否则下次 S1 重启服务器会继续以 slave 角色运行。
6. 将来 M 重新上线后，可以将其配置成 S1 的 slave，然后修改应用程序请求的目标列表，添加上新上线的 M，如将 M 加入到 MySQL 代理的读目标列表。

注意：`reset master`很重要，如果不是基于 GTID 复制且开启了`log-slave-updates`选项时，S1 在应用 relay log 的时候会将其写入到自己的 binlog，以后 S2 会复制这些日志导致重复执行的问题。

其实上面只是提供一种 slave 升级为 Master 的解决思路，在实际应用中环境可能比较复杂。例如，上面的 S1 是 S2 的 master，这时 S1 如果没有设置为 read-only，当 M 宕机时，可以不用停止 S1，也不需要`reset master`等操作，受影响的操作仅仅只是 S1 一直无法连接 M 而已，但这对业务不会有多大的影响。

相信理解了前面的内容，分析主从切换的思路应该也没有多大问题。

## 6.6 指定不复制到 slave 上的语句

前面说的[筛选要复制的库和表](https://www.cnblogs.com/f-ck-need-u/p/9155003.html#blog6.1)可以用于指定不复制到 slave 上的库和表，但却没有筛选不复制到 slave 的语句。

但有些特殊情况下，可能需要这种功能。例如，master 上创建专门用于复制的用户 repl，这种语句其实没有必要复制到 slave 上，甚至出于安全的考虑不应该复制到 slave 上。

可以使用`sql_log_bin`变量对此进行设置，默认该变量的值为 1，表示所有语句都写进 binlog，从而被 slave 复制走。如果设置为 0，则之后的语句不会写入 binlog，从而实现"不复制某些语句到 slave"上的功能。

例如：屏蔽创建 repl 用户的语句。

```bash
mysql> set sql_log_bin=0;
mysql> create user repl@'%' identified by 'P@ssword1!';
mysql> grant replication slave on *.* to repl@'%';
mysql> set sql_log_bin=1;
```

在使用该变量时，默认是会话范围内的变量，一定不能设置它的全局变量值，否则所有语句都将不写 binlog。

## 6.7 主从高延迟的解决思路

slave 通过 IO 线程获取 master 的 binlog，并通过 SQL 线程来应用获取到的日志。因为各个方面的原因，经常会出现 slave 的延迟(即`Seconds_Behind_Master`的值)非常高(动辄几天的延迟是常见的，几个小时的延迟已经算短的)，使得主从状态不一致。

一个很容易理解的延迟示例是：假如 master 串行执行一个大事务需要 30 分钟，那么 slave 应用这个事务也大约要 30 分钟，从 master 提交的那一刻开始，slave 的延迟就是 30 分钟，更极端一点，由于 binlog 的记录时间点是在事务提交时，如果这个大事务的日志量很大，比如要传输 10 多分钟，那么很可能延迟要达到 40 分钟左右。而且更严重的是，这种延迟具有滚雪球的特性，从延迟开始，很容易导致后续加剧延迟。

所以，第一个优化方式是不要在 mysql 中使用大事务，这是 mysql 主从优化的第一口诀。

在回归正题，要解决 slave 的高延迟问题，先要知道`Second_Behind_Master`是如何计算延迟的：SQL 线程比 IO 线程慢多少(其本质是 NOW()减去`Exec_Master_Log_Pos`处设置的 TIMESTAMP)。在主从网络状态良好的情况下，IO 线程和 master 的 binlog 大多数时候都能保持一致(也即是 IO 线程没有多少延迟，除非事务非常大，导致二进制日志传输时间久，**但 mysql 优化的一个最基本口诀就是大事务切成小事务** )，所以在这种理想状态下，可以认为主从延迟说的是 slave 上的数据状态比 master 要延迟多少。它的计数单位是秒。

1. **从产生 Binlog 的 master 上考虑，可以在 master 上应用 group commit 的功能，并设置参数 binlog_group_commit_sync_delay 和 binlog_group_commit_sync_no_delay_count，前者表示延迟多少秒才提交事务，后者表示要堆积多少个事务之后再提交。这样一来，事务的产生速度降低，slave 的 SQL 线程相对就得到缓解**。

2. **再者从 slave 上考虑，可以在 slave 上开启多线程复制(MTS)功能，让多个 SQL 线程同时从一个 IO 线程中取事务进行应用，这对于多核 CPU 来说是非常有效的手段**。但是前面介绍多线程复制的时候说过，没有掌握多线程复制的方方面面之前，千万不要在生产环境中使用多线程复制，要是出现 gap 问题，很让人崩溃。

3. 最后从架构上考虑。主从延迟是因为 slave 跟不上 master 的速度，那么可以考虑对 master 进行节流控制，让 master 的性能下降，从而变相提高 slave 的能力。这种方法肯定是没人用的，但确实是一种方法，提供了一种思路，比如 slave 使用性能比 master 更好的硬件。另一种比较可取的方式是加多个中间 slave 层(也就是 master->slaves->slaves)，让多个中间 slave 层专注于复制(也可作为非业务的他用，比如用于备份)。

4. 使用组复制或者 Galera/PXC 的多写节点，此外还可以设置相关参数，让它们对延迟自行调整。但一般都不需要调整，因为有默认设置。

还有比较细致的方面可以降低延迟，比如设置为 row 格式的 Binlog 要比 statement 要好，因为不需要额外执行语句，直接修改数据即可。比如 master 设置保证数据一致性的日志刷盘规则(sync_binlog/innodb_flush_log_at_trx_commit 设置为 1)，而 slave 关闭 binlog 或者设置性能优先于数据一致性的 binlog 刷盘规则。再比如设置 slave 的隔离级别使得 slave 的锁粒度放大，不会轻易锁表(多线程复制时避免使用此方法)。还有很多方面，选择好的磁盘，设计好分库分表的结构等等，这些都是直接全局的，实在没什么必要在这里多做解释。
