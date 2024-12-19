# 当我们在讨论CQRS时，我们在讨论些神马？

当我写下这个标题的时候，我就有些后悔了，题目有点大，不太好控制。但我还是打算尝试一下，通过这篇内容来说清楚CQRS模式，以及和这个模式关联的其它东西。希望我能说得清楚，你能看得明白，如果觉得不错，右下角点个推荐！

先从CQRS说起，CQRS的全称是Command Query Responsibility Segregation，翻译成中文叫作命令查询职责分离。从字面上就能看出，这个模式要求开发者按照方法的职责是命令还是查询进行分离，什么是命令？什么是查询？我们来继续往下看。

## Query & Command

**什么是命令？什么是查询？**

- 命令(Command):不返回任何结果(void)，但会改变对象的状态。
- 查询(Query):返回结果，但是不会改变对象的状态，对系统没有副作用。

**对象的状态是什么意思呢？**

对象的状态，我们可以理解成它的属性，例如我们定义一个Person类，定义如下：

```java
public class Person {
    public string Id { get; set; }
    public string Name { get; set; }
    public int Age { get; set; }
    public void Say(string word) {
        Console.WriteLine($"{Name} Say: {word}");
    }
}
```

在Person类中：

- Name、Age：属性（状态）
- Say(string): 方法（行为）

再回到本小节讨论的内容，是不是就很好理解了呢？当我定义一个方法，要改变Person实例的Name或Age的时候，这个方法就属于Command；如果定一个方法，只查询Person实例信息的时候，这个方法就属于Query。当我们按照职责将Command和Query进行分离的时候，你就在使用CQRS模式了。

**其实这就是CQRS的全部。** 有朋友可能要说了，如果这就是CQRS的全部，也太过于简单了吧？是的，大道至简！

## 读写分离

当我们按照CQRS进行分离以后，你是不是已经看出来，这玩意儿太适合做读写分离了？当我们的数据库是主从模式的时候，主库负责写入、从库负责读取，完全匹配Command和Query，简直完美。那么我们接下来就说一下读写分离。

现在主流的数据库都支持主从模式，主从模式的好处是方便我做故障迁移，当主库宕机的时候，可以快速的启用从库，从而减小系统不可用时间。

当我们在使用数据库主从模式的时候，如果应用程序不做读写分离，你会发现从库基本上没用，主库每天忙的要死，既要负责写入，又要负责查询，遇见访问量大的时候CPU飙升是常有的事。然而从库就太闲了，除了接收主库的变更记录做数据同步，再没有别的事情可做，不管主库压力多大，从库的CPU一直跟心电图似的0-1-0-1...当我们读写分离以后，主库负责写入，从库负责读取，代码要怎么改呢？我们只需要定义两个Repository就可以了：

```java
public interface IWritablePersonRepository {
    //写入数据的方法
}
public interface IReadonlyPersonRepository {
    //读取数据的方法
}
```

在IWritablePersonRepository中使用主库的连接，IReadonlyPersonRepository中使用从库的连接。然后，在Command里面使用IWritablePersonRepository， 在Query里面使用IReadonlyPersonRepository，这样就在应用层实现了读写分离。

## CRUD和EventSourcing

说到CQRS，不可避免的要说到这两个数据操作模型。为什么要说数据操作模型呢？因为数据操作严重影响性能，而我们分离的一个重要目的就是要提高性能。

### CRUD

CRUD（Create、Read、Update、Delete）是 **面向数据** 的，它将对数据的操作分为创建、更新、删除和读取四类，这四个操作可以对应我们SQL语句中的insert、select、update、delete，非常直观明了，它的存在就是操作数据的。

因为存在即合理，我们不能片面的说CRUD是好或者坏，这里只简单说一下它存在的问题：

- 并发冲突：这是个大问题，当A和B同时更新一行记录的时候，你的事务必然报错。
- 丢失数据操作的上下文：这个问题也不小，对于开发者来说，我们通常要知道数据是谁在什么时候做了什么更新，但是CURD只存储了最终的状态，对数据操作的上下文一无所知。

好了，更多的问题不再列举，单是“并发冲突”这一个问题，在高并发的环境下就不适用。既然CRUD不适用，我们在构建高性能应用的时候，就只能寄希望于ES了。

### Event Souring

Event Souring，翻译过来叫事件溯源。什么意思呢？它把对象的创建、修改、删除等一系列的操作都当作事件（_注意：事件和命令还有区别，后面会讲到_），持久化的时候只存储事件，存储事件的介质叫做 **EventStore** ，当要获取一个对象的最新状态时，通过EventStore检索该对象的所有Event并重新加载来获取对象的最新状态。EventStore可以是数据库、磁盘文件、MongoDB等，由于Event的存储都是新增的，所以不存在并发冲突的问题。

## Command和Event

在CQRS+ES的方案中，我们要面对这两个概念，命令和事件。

- Command：描述了用户的意图。
- Event：描述了对象状态的改变。

我们举一个例子，比如说你要更新自己的个人资料，例如将Age由35修改为18，那么对应的命令为：

```java
public class PersonUpdateCommand {
    public string Id { get; set; }
    public int Age{ get; set; }
    public PersonUpdateCommand(string id, int age){
        this.Id = id;
        this.Age = age;
    }
}
```

PersonUpdateCommand是一个命令，它描述了用户更新个人资料的意图。当程序接收到这个命令以后，就需要对数据更改，从而引发数据状态变化，产生Event：

```java
public class PersonAgeChangeEvent {
    public string Id { get; private set; }
    public int Age{ get; private set; }
    public PersonAgeChangeEvent(string id, int age){
        this.Id = id;
        this.Age = age;
    }
}
public class PersonUpdateCommandHandler {
    private PersonUpdateCommand Command;
    public PersonUpdateCommandHandler(PersonUpdateCommand command) {
        this.Command = command;
    }
    public void Handle() {
        var person = GetPersonById(Command.Id);
        if(person.Age != Command.Age) {
            //生成并发送事件
            var @event = new PersonAgeChangeEvent(Command.Id, Command.Age);
            EventBus.Send(@event);
        }
    }
}
```

## 数据一致性

常见的数据一致性模型有两种：强一致性和最终一致性。

- 强一致性：在任何时刻所有的用户或者进程查询到的都是最近一次成功更新的数据。
- 最终一致性：和强一致性相对，在某一时刻用户或者进程查询到的数据可能有不同，但是最终成功更新的数据都会被所有用户或者进程查询到。

说到一致性的问题，我们就不得不说一下CAP定理。

### CAP定理

1998年，加州大学的计算机科学家 Eric Brewer 提出，分布式系统有三个指标。

- Consistency：一致性
- Availability：可用性
- Partition tolerance：分区容错

它们的第一个字母分别是 C、A、P，这三个指标不可能同时做到。这个结论就叫做 CAP 定理。

对于分布式系统来说，受CAP定理的约束，最终一致性就成了唯一的选择。实现最终一致性要考虑以下问题：

- 重试策略：在分布式系统中，我们无法保证每一次操作都能被成功的执行，例如网络中断、服务器宕机等临时性的错误，都会导致操作执行失败，那么我们就要等待故障恢复后进行重试。重试的操作对于系统来说可能会造成一些副作用，例如你正在支付的时候网络中断了，这个时候你不知道是否支付成功，联网以后再次重试，可能就会造成重复扣款。如果要避免重试造成的系统危害，就要将操作设计为幂等操作。
- - **幂等性** ：简单的说，就是一个操作执行一次和执行多次产生的结果是一样的，不会产生副作用。
- 撤销策略：与重试策略相对应的，如果一个操作最终确定执行失败，那么我们需要撤销这个操作，将系统还原到执行该操作之前的状态。撤销操作有两种，一种是直接将对象修改为执行前的状态，这种情况将造成数据审计不一致的问题；另一种是类似于财务上的红冲操作，新增一个命令，冲掉上一个操作，从而保证数据的完整性，并能够满足数据审计的要求。

## Messaging

通过上面的介绍，我们已经知道在一个系统中所有的改变都是基于操作和由操作产生的事件所引发的。消息可以是一个Command，也可以是一个Event。当我们基于消息来实现CQRS中的命令和事件发布的时候，我们的系统将会更加的灵活可扩展。

如果你的系统基于消息，那么我猜你离不开消息总线，我在[《手撸一套纯粹的CQRS实现》](https://www.cnblogs.com/youring2/p/10991338.html)中写了一个基于内存的CommandBus的实现，感兴趣的朋友可以去看一下，CommandBus的代码定义如下：

```java
public class CommandBus : ICommandBus {
    private readonly ICommandHandlerFactory handlerFactory;
    public CommandBus(ICommandHandlerFactory handlerFactory) {
        this.handlerFactory = handlerFactory;
    }
    public void Send<T>(T command) where T : ICommand {
        var handler = handlerFactory.GetHandler<T>();
        if (handler == null)
        {
            throw new Exception("未找到对应的处理程序");
        }
        handler.Execute(command);
    }
}
```

基于内存的消息总线只能用于开发环境，在生产环境下不能够满足我们分布式部署的需要，这个时候就需要采用基于消息队列的方式来实现了。消息队列有很多，例如Redis的订阅发布、RabbitMQ等，消息总线的实现也有很多优秀的开源框架，例如Rebus、Masstransit等，选一个你熟悉的框架即可。

## 数据审计

数据审计是CQRS带给我们的另一个便利。由于我们存储了所有事件，当我们要获取对象变更记录的时候，只需要将EventStore中的记录查询出来，便可以看到整个的生命周期。这种操作，简直比打开了你青春期的日记本还要清晰明了。

当然，如果你要想知道对象的操作审计日志怎么办？同样的道理，我们记录下所有的Command就可以了。那所有查询日志呢？哈哈，不要调皮了。记录的东西越多，你的存储就越大，如果你的存储空间允许的话，当然是越详细越好的，主要还是看业务需求。

如果我们记录了所有Command，我们还可以有针对性的进行分析，哪些命令使用量大、哪些命令执行时间长。。这些数据将对我们的扩容提供数据支撑。

## 分组部署

在分布式系统中，Command和Query的使用比例是不一样的，Command和Command之间、Query和Query之间的权重也存在差异，如果单纯的将这些服务平均的部署在每一个节点上，那纯粹就是瞎搞。一个比较靠谱的实践是将不同权重的Command和Query进行分组，然后进行有针对性的部署。

## 总结

CQRS很简单，如何用好CQRS才是关键。CQRS更像是一种思想，它为我们提供了系统分离的基本思路，结合ES、Messaging等模式，为构建分布式高可用可扩展的系统提供了良好的理论依据。

园子里有很多钻研CQRS+ES的前辈，本文借鉴了他们的文章和思想，感谢他们的分享！

文章中有任何不准确或错误的地方，请不吝赐教！欢迎讨论！

## 参考文档

- [https://www.cnblogs.com/yangecnu/p/Introduction-CQRS.html](https://www.cnblogs.com/yangecnu/p/Introduction-CQRS.html)
- [https://www.cnblogs.com/netfocus/p/4150084.html](https://www.cnblogs.com/netfocus/p/4150084.html)
- [http://www.ruanyifeng.com/blog/2018/07/cap.html](https://www.ruanyifeng.com/blog/2018/07/cap.html)
- [https://docs.microsoft.com/en-us/previous-versions/msp-n-p/dn589800(v=pandp.10)](<https://docs.microsoft.com/en-us/previous-versions/msp-n-p/dn589800(v=pandp.10)>)
- [https://msdn.microsoft.com/magazine/mt238399](https://msdn.microsoft.com/magazine/mt238399)
