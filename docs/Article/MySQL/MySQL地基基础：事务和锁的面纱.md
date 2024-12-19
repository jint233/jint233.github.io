# MySQL 地基基础：事务和锁的面纱

### 什么是事务，为什么需要事务

在 MySQL 中，事务是由一条或多条 SQL 组成的单位，在这个单位中所有的 SQL 共存亡，有点有福同享，有难同当的意思。要么全部成功，事务顺利完成；要么只要有一个 SQL 失败就会导致整个事务失败，所有已经做过的操作回退到原始数据状态。

### 用日常细说事务的特性

首先我们先说一下事务的四个特性：ACID。

- A：原子性（atomicity），一个事务要么全都成功，要么全都失败
- C：一致性（consistency），在事务的整个生命周期里，查询的数据是一致的，保证数据库不会返回未提交的事务的数据
- I：隔离性（isolation），一个事务所做的操作，在最终提交前，对其他事务是不可见的，保证事务与事务之间不会冲突
- D：持久性（durability），只要事务提交，数据就不会丢失，即使系统崩溃，事务也已经完成

在日常生活中有很多的事情就能体现为数据库中的事务。比如“转账”，下面我们就具体展开，你就可以很清晰的认识事务的四个特性。

- 时间：2020 年 1 月 1 日
- 地点：某银行 ATM
- 人物：A 和 B
- 起因：B 向 A 借 1000 元人民币
- 经过：A 转账给 B
- 结果：转账成功或失败

这么一个转账我们想一下底层基本的技术支撑与实现，B 向 A 借钱，A 要转账给 B，首先 A 必须有大于 1000 元的余额，然后从 A 的账户减 1000 元，在 B 的账户里加 1000 元。

我们定义一个事务：

```sql
获取 A 账户余额
select balance from account where username='A';
在 A 账户里减 1000 元
update account set balance=balance-1000 where username='A';
获取 B 账户余额
select balance from account where username='B';
在 B 账户里加 1000 元
update account set balance=balance+1000 where username='B';
```

好了，一个简单事务基本就这样，我们开始分析分析这个事务是如何保证事务的 ACID 的。

- **原子性** ：这个事务要么全成功，要么全失败。事务成功则 1000 元转账到了 B 账户，事务失败回滚则 1000 元还在 A 账户里，就是说 1000 元不能凭空消失。
- **一致性** ：在这个事务中，所有的查询都是一致的，我们先查询 A 账户余额是否大于 1000，如果小于 1000，事务失败回滚；如果获取不到 B 账户余额，事务失败回滚。
- **隔离性** ：在这个事务发生的同时，发生了另一个事务（A 通过手机银行将钱全部转移到另外的账户，比如一共有 1500 元），第一个事务转 1000 元，第二个事务转 1500 元，我们仔细想想，如果都成功，那岂不是凭空获取了 1000 元，这是不合理的，每个事务在执行前都应查一下余额是否够本次转账的。这两个事务应该是隔离的，不能有冲突。
- **持久性** ：转账成功了（即事务完成），这代表钱已经发生了转移，这个时候发生 ATM 吞卡、ATM 断电、手机银行无法登陆等等一切故障，反正钱已经转走了，钱没有丢（即数据没有丢）

### MySQL 并发控制技术

并发控制技术可以说是数据库的底层基础技术，并发控制技术可以拆分来看，一是并发，一是控制。并发也就是说大量请求连接到数据库，控制就是数据库要控制好这些连接，保证资源的可用性、安全性，解决资源的挣用的问题。

那么如何实现并控制呢？主要通过两个方面：

- Lock
- MVCC

先分别简单说一下 Lock 和 MVCC，具体的后面再聊。

- Lock，并发连接到数据库，操作有读和读、读和写、写和写，锁来保证并发连接使得数据可以保持一致性。
- MVCC（Multiversion Concurrency Control），多版本并发控制，是数据库的多版本，可以提高并发过程中的读和写操作，有效的避免写请求阻塞读请求。

### 面试再也不怕被问到的 MVCC

前面我们已经大致了解了 MVCC 是什么，以及他做什么事情，现在我们具体看看 MVCC 是如何工作的？

我们知道数据的一致性，可以通过锁来保证，在并发连接中，锁机制在读和读的并发请求中不会锁数据，但是在读和写的并发请求中，写请求会加锁，读请求会被写请求阻塞，基于此，MVCC 发挥其作用。

MVCC 控制两类操作：

- 快照读：读取的是历史可见版本的数据，无锁
- 当前读：读取的是当前最新版本的数据，加锁

我们举个例子说一下吧，比如:

```sql
mysql> create table tab1(id decimal,name varchar(10),address varchar(10),status decimal,primary key(id));
mysql> insert into tab1 values(1,'a','beijing',1); 
```

表中数据为：

id

name

address

status

1

a

beijing

1

现在有一个请求，将数据 a 的地址改为 shanghai，这个数据更新的过程，我们细化一下，将历史数据置为失效，将新的数据插入：

```sql
mysql> update tab1 set status=0 where name='a';
mysql> insert into tab1 value(2,'a','shanghai',1);
```

表中数据为：

id

name

address

status

1

a

beijing

0

2

a

shanghai

1

MVCC 的原理就类似是这样的，`address='beijing'` 就是历史数据，更新前保存了下来，`address='shanghai'` 就是当前数据，新插入数据，这样并发连接来了，既可以读取历史数据，也可以修改当前数据。比如，现在有三个事务：

- T1 -> 要执行 update address
- T2 -> 要执行 update address
- T3 -> 要执行 update address

T1 先获取了表中这一行数据，执行了 update，未提交；T2 获取表中这一行数据，由于 T1 未提交，address='beijing',这个 beijing 就来源历史数据；T3 也获取表中这一行数据，由于 T1 未提交，`address='beijing'`，这个 beijing 也来源历史数据。这样是不是好理解了。

以此类推，如果只对 `name='a'` 这一行数据有 N 个并发连接要做 M 个操作，这些历史数据都保存在表中，这个表的数据量无法预估，势必会造成压力与瓶颈。多版本数据到底如何保存，这就不是本节考虑的问题了，是数据库 undo 帮你做的工作。这里就不展开了。（后期可能会做 undo 相关的 chat，大家可以关注我）

### 简单易懂的实例帮你理解 MySQL 事务隔离级别

事务隔离级别，拆分来看，事务、隔离、级别，故是三个概念的集合，是保证事务之间相互隔离互不影响的，有多个级别。事务在执行过程中可能会出现脏读、不可重复读、幻读，那么 MySQL 的事务隔离级别到底有怎样的表现呢？

事务隔离级别

脏读

不可重复读

幻读

读未提交(Read-Uncommited)

可能

可能

可能

读提交(Read-Commited)

不可能

可能

可能

可重复读交(Repeatable-Read)

不可能

不可能

可能

序列化(Serializable)

不可能

不可能

不可能

那么到底什么是脏读、不可重复读、幻读呢？

- **脏读** ：一个事务读取了另一个未提交事务操作的数据。
- **不可重复读** ：一个事务重新读取前面读取过的数据时，发现该数据已经被修改了或者不见了，其实已被另一个已提交的事务操作了。解决了脏读的问题。
- **幻读** ：一个事务，需要更新数据，于是重新提交了一个查询，返回符合查询条件行，发现这些行因为其他提交的事务发生了改变，这些数据像“幻影”一样出现了。解决了不可重复读。

接下来我们用具体实例分析各个事务隔离级别。

创建测试表 t_account：

```sql
mysql> create table t_account(name varchar(10),balance decimal);
mysql> insert into t_account values('A',100);
mysql> insert into t_account values('B',0);
```

#### 读未提交

设置事务隔离级别：

```plaintext
mysql> set global tx_isolation='read-uncommitted';          
```

查询事务隔离级别：

```sql
mysql>  SELECT @@tx_isolation;
+------------------+
| @@tx_isolation   |
+------------------+
| READ-UNCOMMITTED |
+------------------+
1 row in set (0.00 sec)
```

**当前事务可以读取另一个未提交事务操作的数据。**

环境：用户 A 有 100 元钱，给用户 A 增加 100 元，然后用户 A 转账给用户 B。

事务 1

事务 2

begin;

begin;

update t\_account set balance=balance+100 where name='A'; #给用户 A 增加 100 元

select balance from t\_account where name='A'; #转账前查询用户 A 余额为 200 元

rollback; #决定不给用户 A 增加 100 元了，事务回滚

update t\_account set balance=balance-200 where name='A'; #用户 A 继续给用户 B 转账，用户 A 减 200 元

update t\_account set balance=balance+200 where name='B'; #用户 A 继续给用户 B 转账，用户加加 200 元

commit; #提交事务

现在我们查询一下用户 A 和用户 B 的余额：

```sql
mysql> select * from t_account;
+------+---------+
| name | balance |
+------+---------+
| A    |    -100 |
| B    |     200 |
+------+---------+
2 rows in set (0.00 sec)
```

问题来了，这个结果不符合预期，用户 A 竟然是 -100 元，用户 B 增加了 200 元，这是因为事务 2 读取了事务 1 未提交的数据。

#### 读提交

设置事务隔离级别：

```plaintext
mysql> set global tx_isolation='read-committed';
```

查询事务隔离级别：

```sql
mysql>  SELECT @@tx_isolation;
+------------------+
| @@tx_isolation   |
+------------------+
| READ-COMMITTED    |
+------------------+
1 row in set (0.00 sec)
```

**当前事务只能读取另一个提交事务操作的数据。**

环境：用户 A 有 100 元钱，给用户 A 增加 100 元。

事务 1

事务 2

begin;

begin;

update t\_account set balance=balance+100 where name='A'; #给用 A 增加 100 元

select \* from t\_account where name='A'; #事务 2 查用户的余额，因事务 1 未提交，仍为 100 元

commit;

select \* from t\_account where name='A'; #事务 2 查用户的余额，事务 1 已提交，变为 200 元

一个事务重新读取前面读取过的数据时，发现该数据已经被修改了，其实已被另一个已提交的事务操作了。

#### 可重复读

设置事务隔离级别：

```plaintext
mysql> set global tx_isolation='repeatable-read';
```

查询事务隔离级别：

```sql
mysql>  SELECT @@tx_isolation;
+------------------+
| @@tx_isolation   |
+------------------+
| REPEATABLE-READ  |
+------------------+
1 row in set (0.00 sec)
```

**当前事务读取通过第一次读取建立的快照是一致的，即使另外一个事务提交了该数据。除非自己这个事务可以读取在自身事务中修改的数据。**

可重复读隔离级别是 MySQL 的默认隔离级别。

环境：用户 A 有 100 元钱，给用户 A 增加 100 元。

事务 1

事务 2

begin;

begin;

select \* from t\_account where name='A'; #事务 2 查用户的余额，为 100 元

update t\_account set balance=balance+100 where name='A'; #给用 A 增加 100 元

select \* from t\_account where name='A'; #事务 2 查用户的余额，因事务 1 未提交，仍为 100 元

commit;

select \* from t\_account where name='A'; #事务 2 查用户的余额，事务 1 已提交，仍为 100 元

这就能看出来，事务 2 开启后读取了用户 A 的余额，即使事务 1 修改了数据，不管提交与否，事务 2 读取的数据一直是之前第一次读取的数据。继续操作。

事务 1

事务 2

commit;

select \* from t\_account where name='A'; ###事务 2 查用户的余额，为 200 元

为什么现在变成了 200 元了，因为事务 2 已经 commit，再次 select 是一个新的事务，读取数据当然又变为第一次获取数据（此时的数据是最新的数据）。

思考一下：上述这个举例是可重复读的 select 相关验证，如果是 DML 操作，会不会是同样的结果呢？

思考三分钟......

答案是：其他事物即使查询不到的数据，DML 操作也可能会影响那些提交的数据。好，让我验证一下。

update 操作：

事务 1

事务 2

begin;

begin;

select \* from t\_account; #有一行数据，用户 A，余额 100 元

insert into t\_account values('B',100); #增加用户 B，余额 100 元

commit;

select \* from t\_account where name='B'; #无返回行，查询不到用户 B

update t\_account set balance=balance+100 where name='B'; #神奇，更新成功了

select \* from t\_account; #用户 A 余额 100，用户 B 余额 200

select \* from t\_account; #用户 A 余额 100，用户 B 余额 100

commit;

select \* from t\_account; #用户 A 余额 100，用户 B 余额 200

delete 操作：

事务 1

事务 2

begin;

begin;

select \* from t\_account; #有 2 行数据，用户 A 余额 100 元，用户 B 余额 200

insert into t\_account values('C',100); #增加用户 C，余额 100 元

commit;

select \* from t\_account where name='C'; #无返回行，查询不到用户 C

delete from t\_account where name='C'; #神奇，删除成功了

select \* from t\_account; #用户 A 余额 100，用户 B 余额 200

select \* from t\_account; #用户 A 余额 100，用户 B 余额 200，用户 C 余额 100

commit;

select \* from t\_account; #户 A 余额 100，用户 B 余额 200

通过这两个例子你是不是了解了一个事务的 update 和 delete 操作了另外一个事务提交的数据，会使得这些数据在当前事务变得可见。就像幻影一下出现了！

#### 序列化

设置事务隔离级别：

```plaintext
mysql> set global tx_isolation='serializable';
```

查询事务隔离级别：

```sql
mysql>  SELECT @@tx_isolation;
+------------------+
| @@tx_isolation   |
+------------------+
| SERIALIZABLE     |
+------------------+
1 row in set (0.00 sec)
```

**当前事务 select 和 DML 操作的数据都会加行锁，其他事务访问同样的数据需要等锁释放。**

环境：用户 A 有 100 元钱，给用户 A 增加 100 元。

事务 1

事务 2

begin;

begin;

select \* from t\_account where name='A'; #查询用户余额

update t\_account set balance=balance+100 where name='A'; #给用户 A 增加 100 元，执行一直处于等待

commit;

update 成功返回

select \* from t\_account where name='A'; #用户 A 余额为 100，因为事务 2 还未提交，获取的是 undo 中的历史版本数据

begin;

select \* from t\_account where name='A'; #新开一个事务，由于事务 2 还未提交，此查询锁等

commit;

select \* from t\_account where name='A'; #用户 A 余额 200

好了，实例讲解到此结束，是否已经帮你理解了 MySQL 事务隔离级别。

另外，结合前面说的 MVCC，Read-Committed 和 Repeatable-Read，支持 MVCC；Read-Uncommitted 由于可以读取未提交的数据，不支持 MVCC；Serializable 会对所有读取的数据加行锁，不支持 MVCC。

### MySQL 锁机制（机智）

锁是可以协调并发连接访问 MySQL 数据库资源的一种技术，可以保证数据的一致性。锁有两个阶段：加锁和解锁，InnoDB 引擎的锁主要有两类。

**共享锁（S）**

允许一个事务读取数据，阻塞其他事务想要获取相同数据。共享锁之间不互斥，读和读操作可以并行。代码展示：

```sql
select * from table where ... lock in share mode
```

**排它锁（X）**

持有排他锁的事务可以更新数据，阻塞其他事务获取数据的排他锁和共享锁。排它锁之间互斥，读和写、写和写操作不可以并行。代码展示：

```sql
select * from table where ... for update;
```

从 MySQL 数据库的内外区分锁，有两种锁。

**内部锁**

MySQL 在数据库内部自动管理，协调并发连接的资源争用。内部锁再具体来看分为：

*   行锁：会话事务将访问的行数据加锁
*   表锁：会话事务将访问的表整体加锁

**外部锁** 会话层使用特殊的手段显示获取锁，阻塞其他会话对数据的操作。我们通过外部操作命令实现外部锁，比如使用 lock table 和 unlock tables。

我们举个例子来描述一下这个过程吧，比如有事务 1 和事务 2，事务 1 锁定了一行数据，加了一个 S 锁；事务 2 想要对整个表加锁，需要判断这个表是否被加了表锁，表中的每一行是否有行锁。仔细想想这个过程是很快呢？还是非常的慢？如果表很小无所谓了，如果表是海量级数据，那糟了，事务 2 势必耗费很多资源。

如何解决事务 2 这种检索资源消耗的问题呢？事务意向锁帮你先获取意向，先一步问问情况，然后再获取我们想要的 S 和 X 锁，具体分为： **意向共享锁（IS）** 事务 1 说：我要加一个行锁，我有这个意向，你们其他人有没有意见，如果没有我就先拿这个 IS 锁了。 **意向排它锁（IX）**

事务 2 说：我要加一个表锁，这个可是排他锁，我拿了你们就等我用完再说吧，我有这个意向，你们其他人有没有意见，如果没有我就先拿这个 IX 锁了。

前面这个举例，其过程升级优化为：

*   事务 1 先申请获取 IS 锁，成功后，获取 S 锁
*   事务 2 发现表中有 IS 锁了，事务 2 获取表锁会被阻塞

那么这四个锁之间兼容性如何呢？

X

S

IX

IS

X

冲突

冲突

冲突

冲突

S

冲突

兼容

冲突

兼容

IX

冲突

冲突

兼容

兼容

IS

冲突

兼容

兼容

兼容

### 聊几个经典死锁案例

在实际应用中经常发生数据库死锁的情况，那么什么是死锁呢？说白了就是事务 1 锁事务 2，事务 2 锁事务 1，这两个事务都在等着对方释放锁资源，陷入了死循环。

接下来我们介绍几个经典死锁案例，MySQL 默认级别使用的是 REPEATABLE-READ。

#### 场景 1：insert 死锁

创建一个测试表：

```sql
mysql> create table t_insert(id decimal,no decimal,primary key(id),unique key(no));
```

session1：

```sql
mysql> begin;
mysql> insert into t_insert values(1,101);
```

session2：

```sql
mysql> begin;
mysql> insert into t_insert values(2,101);
```

此时会话一直等待无响应。

session1：

```sql
mysql> insert into t_insert values(3,100);
```

结果如下。

此时 session2 立马报出来死锁：

```plaintext
ERROR 1213 (40001): ==Deadlock== found when trying to get lock; try restarting transaction
```

数据库中 insert 作为最简单的 SQL，为什么会导致死锁呢？

session1 在插入(1,101) 的时候会加一个 X 锁；session2 插入(2,101)，no 字段有着唯一性，故 session2 在插入时数据库会做 duplicate 冲突检测，由于事务冲突先加 S 锁；然后 session1 又插入了 (3,100)，此时 session1 会加 insert intention X 锁（插入意向锁），之前 session1 已经有了 X 锁，故进入等待队列，结局就是 session1 和 session2 都在等待，陷入了僵局，MySQL 很机智，牺牲一方事务解决这个尴尬的局面，所以 session2 被干掉了，报错死锁。

#### 场景 2：自增列死锁

自增列死锁问题和场景 1 的类似，比如将场景 1 的主键属性改为自增长属性，主键自增仍唯一，场景模拟类似，加锁的过程也类似，产生死锁的过程也类似，这里就不详细模拟了。

#### 场景 3：rollback 死锁

创建一个测试表：

```sql
mysql> create table t_rollback(id decimal,no decimal,primary key(id),unique key(no));
```

session1：

```sql
mysql> begin;
mysql> insert into t_rollback values(1,100);
```

session2：

```sql
mysql> begin;
mysql> insert into t_rollback values(2,100);
```

此时会话一直等待无响应。

session3

```sql
mysql> begin;
mysql> insert into t_rollback values(3,100);
```

此时会话一直等待无响应。

session1

```plaintext
mysql> rollback;
```

结果如下： 此时 session1 执行了 rollback 成功返回，session2 的 insert 返回成功，session3 立马报出来死锁。

```plaintext
ERROR 1213 (40001): ==Deadlock== found when trying to get lock; try restarting transaction
```

为什么我回滚了事务，还要报死锁，难道我需要全部回滚吗？

session1 在插入 (1,100) 的时候会加一个 X 锁；session2 插入 (2,100)，no 字段有着唯一性，故 session2 在插入时数据库会做 duplicate 冲突检测，由于事务冲突先加 S 锁；session3 插入 (3,100)，no 字段有着唯一性，故 session3 在插入时数据库会做 duplicate 冲突检测，由于事务冲突先加 S 锁；session1 回滚，session2 申请 insert intention X 锁，等 session3;session3 申请 insert intention X 锁，等 session2，结局就是 session2 和 session3 都在等待，陷入了僵局，MySQL 很机智，牺牲一方事务解决这个尴尬的局面，所以 session3 被干掉了，报错死锁。

#### 场景 4：commit 死锁

创建一个测试表：

```sql
mysql> create table t_commit(id decimal,no decimal,primary key(id),unique key(no));
mysql> insert into t_commit values(1,100);
```

session1：

```sql
mysql> begin;
mysql> delete from t_commit where id=1;
```

session2：

```sql
mysql> begin;
mysql> insert into t_commit values(1,100);
```

此时会话一直等待无响应。

session3：

```sql
mysql> begin;
mysql> insert into t_commit values(1,100);
```

此时会话一直等待无响应。

session1：

```plaintext
mysql> commit;
```

结果如下：此时 session1 执行了 commit 成功返回，session3 的 insert 返回成功，session2 立马报出来死锁。

```plaintext
ERROR 1213 (40001): ==Deadlock== found when trying to get lock; try restarting transaction
```

为什么我提交了事务，还要报死锁，难道我需要全部提交吗？

这个产生死锁的过程和场景 3rollback 死锁类似，大家可以和之前的 rollback 死锁产生过程对应来看。

### 小技巧——事务保存点帮你读档重闯关

玩游戏你是不是有过存档、读档的经历，过某一个比较难的关卡，先存档，过不了，就读档重新过。数据库中我们也可以如此，MySQL 事务保存点可以回滚到事务的某时间点，并且不用中止事务。下面举例说明一下。

用户 B 和用户 C 向用户 A 借钱，用户 A 转账给用户 B 和用户 C，转账的过程中发生了用户 C 账户不存在，那么我们也要把转给用户 B 的钱也取消吗？我们可以不取消，使用一个保存点即可。

查询用户 A 有 1000 元：

```sql
mysql> select balance from t_account where name='A';
```

转账 100 元给用户 B：

```sql
mysql> update t_account set balance=balance-100 where name='A';
mysql> update t_account set balance=balance+100 where name='B';
```

**设置事务保存点** 

```plaintext
mysql> savepoint T_A_TO_B;
```

转账 200 元给用户 C：

```sql
mysql> update t_account set balance=balance-200 where name='A';
mysql> update t_account set balance=balance+200 where name='C';
Query OK, 0 rows affected (0.00 sec)
Rows matched: 0  Changed: 0  Warnings: 0
```

发现转账给 C 返回有 0 条受影响的行，转账给 C 未成功，此时用户 A 已经少了 200 元了，先退 200 元再排查吧，转账给用户 B 的不需要重新操作了。

```plaintext
mysql> rollback to T_A_TO_B;
mysql> commit；
```

根据提示 0 条受影响的行，也就是说用户 C 不存在呀，我们查询一下个用户信息：

```sql
mysql> select *from t_account where name='A';
+------+---------+
| name | balance |
+------+---------+
| A    |     900 |
+------+---------+
1 row in set (0.00 sec)
mysql> select* from t_account where name='B';
+------+---------+
| name | balance |
+------+---------+
| B    |     200 |
+------+---------+
1 row in set (0.00 sec)
mysql> select * from t_account where name='C';
Empty set (0.00 sec)
```

结果：用户 A 成功转 100 元给用户 B，用户 C 果然不存才，设置了保存点，帮我们省了很多工作，中途不用取消全部操作。

### 小技巧——一个死锁的具体分析方法

前面我们学习了事务、锁，以及介绍了几个经典死锁案例，当遇到死锁，我们怎样具体分析呢？

分析死锁，我们就需要看死锁的日志信息，通过日志具体找到死锁的原因及执行的语句。

首先，我们用前面的场景 1 模拟一个死锁。

然后，执行如下命令获取死锁信息：

```plaintext
mysql> show engine innodb status;
```

在打印的日志中，先看事务 1 的日志：

```sql
***(1) TRANSACTION:
TRANSACTION 2179, ACTIVE 8 sec inserting
mysql tables in use 1, locked 1
LOCK WAIT 2 lock struct(s), heap size 1136, 1 row lock(s), undo log entries 1
MySQL thread id 32, OS thread handle 140317789804288, query id 823 localhost root update
insert into t_insert values(2,101)*** (1) WAITING FOR THIS LOCK TO BE GRANTED:
RECORD LOCKS space id 37 page no 4 n bits 72 index no of table `test`.`t_insert` trx id 2179 lock mode S waiting
Record lock, heap no 2 PHYSICAL RECORD: n_fields 2; compact format; info bits 0
0: len 5; hex 8000000065; asc     e;;
1: len 5; hex 8000000001; asc      ;;
TRANSACTION 2179, ACTIVE ==8 sec== inserting
```

事务 1 持续了 8 秒：

```sql
mysql ==tables in use 1==, locked 1  涉及一张表\
LOCK WAIT 2 lock struct(s) 有两个锁\
insert into t_insert values(2,101) 这是 SQL 语句\
WAITING FOR THIS LOCK TO BE GRANTED 唯一行锁处于等待\
RECORD LOCKS space id 37 page no 4 n bits 72 index no 加锁的是索引字段 no\
lock mode S waiting 锁等待为 S 锁
```

事务 2 的日志：

```sql
***(2) TRANSACTION:
TRANSACTION 2178, ACTIVE 17 sec inserting
mysql tables in use 1, locked 1
3 lock struct(s), heap size 1136, 2 row lock(s), undo log entries 2
MySQL thread id 33, OS thread handle 140317663659776, query id 824 localhost root update
insert into t_insert values(3,100)*** (2) HOLDS THE LOCK(S):
RECORD LOCKS space id 37 page no 4 n bits 72 index no of table `test`.`t_insert` trx id 2178 lock_mode X locks rec but not gap
Record lock, heap no 2 PHYSICAL RECORD: n_fields 2; compact format; info bits 0
0: len 5; hex 8000000065; asc     e;;
1: len 5; hex 8000000001; asc      ;;
**\* (2) WAITING FOR THIS LOCK TO BE GRANTED:
RECORD LOCKS space id 37 page no 4 n bits 72 index no of table `test`.`t_insert` trx id 2178 lock_mode X locks gap before rec insert intention waiting
Record lock, heap no 2 PHYSICAL RECORD: n_fields 2; compact format; info bits 0
0: len 5; hex 8000000065; asc     e;;
1: len 5; hex 8000000001; asc      ;;
```

*   `HOLDS THE LOCK(S)` 持有锁的内容
*   `lock_mode X locks` 持有锁的锁等待内容是一个 x 锁
*   `WAITING FOR THIS LOCK TO BE GRANTED` 等待锁的内容
*   `lock_mode X locks gap before rec insert intention waiting` 等待锁的锁等待内容也是一个 x 锁

通过这些日志，我们发现日志中的事务 1，持有 S 锁，S 锁的出现是因为需要检查数据唯一性，我们的 no 字段确实有唯一索引，这一点也正好验证了。日志中的事务 1，持有一个 X 锁，又等待一个 X 锁。所以场景 1 中的两个事务都在锁等，造成了死锁。

### 小技巧——换种思路提高事务能力

在数据中如果是单一事务，那没的说，一个一个的事务来执行，毫无压力。现实是不允许这样的，肯定是有大量的并发连接，并发事务在所难免。如果高并发的环境中，事务处理效率肯定大幅下降，这个时候我们有没有方法提高并发事务能力呢？

我们解决技术处理问题的限制，这次我们换一种思路来提高事务能力。比如：

**合理的在线、离线数据库** 比如我们的系统数据量日益增加，还有一些业务需要查询大量的数据，我们可以改造系统为在线、离线数据库，在线表提供高效事务能力，离线表提供数据查询服务，互不影响。 **提高 delete 操作效率的思考**

如果你对表有大量数据的 delete 操作，比如定期的按日、月、年删除数据，可以设计表为日表、月表、年表亦或是相对应的分区表，这样清理数据会由大事务降低为小事务。
```
