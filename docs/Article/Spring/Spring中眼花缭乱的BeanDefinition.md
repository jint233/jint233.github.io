# Spring 中眼花缭乱的 BeanDefinition

#### 引入主题

为什么要读 Spring 源码，有的人为了学习 Spring 中的先进思想，也有的人是为了更好的理解设计模式，当然也有很大一部分小伙伴是为了应付面试，Spring Bean 的生命周期啦，Spring AOP 的原理啦，Spring IoC 的原理啦，应付面试，看几篇博客，对照着看看源码，应该就没什么问题了，但是如果想真正的玩懂 Spring，需要花的时间真的很多，需要你沉下心，从最基础的看起，今天我们就来看看 Spring 中的基础——BeanDefinition。

#### 什么是 BeanDefinition

![image.png](../assets/15100432-b6f3e81ca4e0b5b4.png) Spring 官网中有详细的说明，我们来翻译下： SpringIoc 容器管理一个 Bean 或多个 Bean，这些 Bean 通过我们提供给容器的配置元数据被创建出来（例如，在 xml 中的定义） 在容器中，这些 Bean 的定义用 BeanDefinition 对象来表示，包含以下元数据：

- 全限定类名， 通常是 Bean 的实际实现类；
- Bean 行为配置元素，它们说明 Bean 在容器中的行为（作用域、生命周期回调等等）；
- Bean 执行工作所需要的的其他 Bean 的引用，这些 Bean 也称为协作者或依赖项；
- 其他配置信息，例如，管理连接池的 bean 中，限制池的大小或者使用的连接的数量。

Spring 官网中对 BeanDefinition 的解释还是很详细的，但是不是那么通俗易懂，其实 BeanDefinition 是比较容易解释的：BeanDefinition 就是用来描述一个 Bean 或者 BeanDefinition 就是 Bean 的定义。

创建一个 Java Bean，大概是下面这个酱紫： ![image.png](../assets/15100432-87de503f024f272f.png) 我们写的 Java 文件，会编译为 Class 文件，运行程序，类加载器会加载 Class 文件，放入 JVM 的方法区，我们就可以愉快的 new 对象了。

创建一个 Spring Bean，大概是下面这个酱紫： ![image.png](../assets/15100432-4e677493ee644264.png) 我们写的 Java 文件，会编译为 Class 文件，运行程序，类加载器会加载 Class 文件，放入 JVM 的方法区，这一步还是保持不变（当然这个也没办法变。。。） 下面就是 Spring 的事情了，Spring 会解析我们的配置类（配置文件），假设现在只配置了 A，解析后，Spring 会把 A 的 BeanDefinition 放到一个 map 中去，随后，由一个一个的 BeanPostProcessor 进行加工，最终把经历了完整的 Spring 生命周期的 Bean 放入了 singleObjects。

#### BeanDefinition 类图鸟瞰

![image.png](../assets/15100432-18d3be0ba6b0eda8.png) 大家可以看到，Spring 中 BeanDefinition 的类图还是相当复杂的，我刚开始读 Spring 源码的时候，觉得 BeanDefinition 应该是一个特别简单的东西，但是后面发觉并不是那么回事。

下面我将对涉及到的类逐个进行解读。

#### AttributeAccessor

AttributeAccessor 是一个接口：

```python
/**
 * Interface defining a generic contract for attaching and accessing metadata
 * to/from arbitrary objects.
 *
 * @author Rob Harrop
 * @since 2.0
 */
public interface AttributeAccessor {
 void setAttribute(String name, @Nullable Object value);
 Object getAttribute(String name);
 Object removeAttribute(String name);
 boolean hasAttribute(String name);
 String[] attributeNames();
}
```

我们来看下类上面的注释：接口定义了通用的方法来保存或者读取元数据。既然是接口，那么一定会有实现类，我们先把这个放一边。

#### BeanMetadataElement

BeanMetadataElement 也是一个接口，里面只定义了一个方法：

```plaintext
/**
 * Interface to be implemented by bean metadata elements
 * that carry a configuration source object.
 *
 * @author Juergen Hoeller
 * @since 2.0
 */
public interface BeanMetadataElement {
 @Nullable
 Object getSource();
}
```

我们还是来看下类上的注释：接口提供了一个方法来获取 Bean 的源对象，这个源对象就是源文件，怎么样，是不是不太好理解，没关系，我们马上写个代码来看下：

```java
@Configuration
@ComponentScan
public class AppConfig {
}
@Service
public class BookService {
}
public class Main {
    public static void main(String[] args) {
        AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext(AppConfig.class);
        System.out.println(context.getBeanDefinition("bookService").getSource());
    }
}
file [D:\cycleinject\target\classes\com\codebear\springcycle\BookService.class]
```

怎么样，现在理解了把。

#### AttributeAccessorSupport

AttributeAccessorSupport 类是一个抽象类，实现了 AttributeAccessor 接口，这个 AttributeAccessor 还记得吧，里面定义了通用的方法来保存或者读取元数据的虚方法，AttributeAccessorSupport 便实现了这个虚方法，AttributeAccessorSupport 定义了一个 map 容器，元数据就被保存在这个 map 里面。

##### 为什么要有这个 map

初次读 Spring 源码，看到这个 map 的时候，觉得有点奇怪，元数据不应该是保存在 BeanDefinition 的 beanClass、scope、lazyInit 这些字段里面吗？这个 map 不是多次一举吗？

后面才知道，Spring 是为了方便扩展，不然 BeanDefinition 有新的特性，就要新增字段，这是其一；其二，如果程序员要扩展 Spring，而 BeanDefinition 中定义的字段已经无法满足扩展了呢？

那 Spring 自己有使用这个 map 吗，答案是有的，我们来看下，Spring 在这个 map 中放了什么数据：

```java
    public static void main(String[] args) {
        AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext(AppConfig.class);
        BeanDefinition appConfig = context.getBeanDefinition("appConfig");
        for (String item : appConfig.attributeNames()) {
            System.out.println(item + ":" + appConfig.getAttribute(item));
        }
    }
org.springframework.context.annotation.ConfigurationClassPostProcessor.configurationClass:full
org.springframework.aop.framework.autoproxy.AutoProxyUtils.preserveTargetClass:true
```

可以看到，Spring 在里面放了两个 item：

- 第一个 item 保存着这个配置类是否是一个 Full 配置类，关于 Full 配置类，我在先前的博客有简单的介绍过：[Spring 中你可能不知道的事（二）](https://juejin.im/user/3544481219222488/posts)
- 第二个 item，从名字上就可以知道和 AOP 相关。

### BeanDefinition

BeanDefinition 是一个接口，继承了 AttributeAccessor、BeanMetadataElement，这两个类上面已经介绍过了。

BeanDefinition 定义了很多方法，比如 setBeanClassName、getBeanClassName、setScope、getScope、setLazyInit、isLazyInit 等等，这些方法一眼就知道是什么意思了，这里就不解释了。

### BeanMetadataAttributeAccessor

BeanMetadataAttributeAccessor 继承了 AttributeAccessorSupport，对保存或者读取元数据的方法进行了进一步的封装。

### AbstractBeanDefinition

AbstractBeanDefinition 是一个抽象类，继承了 BeanMetadataAttributeAccessor，实现了 BeanDefinition。

BeanDefinition 实现了 BeanDefinition 定义的大部分虚方法，同时定义了很多常量和默认值。

AbstractBeanDefinition 有三个子类，下面我们来看看这三个子类。

#### ChildBeanDefinition

从 Spring2.5 开始，ChildBeanDefinition 已经不再使用，取而代之的是 GenericBeanDefinition。

#### GenericBeanDefinition

GenericBeanDefinition 替代了 ChildBeanDefinition，ChildBeanDefinition 从字面上，就可以看出有“子 BeanDefinition”的意思，难道 BeanDefinition 还有“父子关系”吗？当然有。

```java
public class ChildService {
    private int id;
    private String name;
    public ChildService(int id, String name) {
        this.id = id;
        this.name = name;
    }
    public int getId() {
        return id;
    }
    public void setId(int id) {
        this.id = id;
    }
    public String getName() {
        return name;
    }
    public void setName(String name) {
        this.name = name;
    }
}
public class ParentService {
    private int id;
    private String name;
    public int getId() {
        return id;
    }
    public void setId(int id) {
        this.id = id;
    }
    public String getName() {
        return name;
    }
    public void setName(String name) {
        this.name = name;
    }
    public ParentService(int id, String name) {
        this.id = id;
        this.name = name;
    }
}
 public static void main(String[] args) {
        AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext();
        GenericBeanDefinition parentBeanDefinition = new GenericBeanDefinition();
        parentBeanDefinition.setScope(BeanDefinition.SCOPE_SINGLETON);
        parentBeanDefinition.setAttribute("name", "codebear");
        parentBeanDefinition.setAbstract(true);
        parentBeanDefinition.getConstructorArgumentValues().addGenericArgumentValue(1);
        parentBeanDefinition.getConstructorArgumentValues().addGenericArgumentValue("CodeBear");
        GenericBeanDefinition childBeanDefinition = new GenericBeanDefinition();
        childBeanDefinition.setParentName("parent");
        childBeanDefinition.setBeanClass(ChildService.class);
        context.registerBeanDefinition("parent", parentBeanDefinition);
        context.registerBeanDefinition("child", childBeanDefinition);
        context.refresh();
        BeanDefinition child = context.getBeanFactory().getMergedBeanDefinition("child");
        for (String s : child.attributeNames()) {
            System.out.println(s + ":" + child.getAttribute(s));
        }
        System.out.println("scope:" + child.getScope());
        System.out.println("-------------------");
        ChildService service = context.getBean(ChildService.class);
        System.out.println(service.getName());
        System.out.println(service.getId());
    }
```

运行结果：

```plaintext
name:codebear
scope:singleton
-------------------
CodeBear
1
```

来分析下代码：

1. 创建了 GenericBeanDefinition 对象 parentBeanDefinition，设置为了单例模式，设置了 Attribute，声明了构造方法的两个参数值；
2. 创建了 GenericBeanDefinition 对象 childBeanDefinition，设置 parentName 为 parent，BeanClass 为 ChildService；
3. 注册 parentBeanDefinition，beanName 为 parent，childBeanDefinition，beanName 为 child；
4. 刷新容器；
5. 从 mergedBeanDefinitions 取出了 child，mergedBeanDefinitions 存放的是合并后的 BeanDefinition；
6. 打印出 child 的 attribute、scope、构造方法的两个参数值。

大家可以看到，childBeanDefinition 继承了 parentBeanDefinition。

如果没有父子关系，单独作为 BeanDefinition，也可以用 GenericBeanDefinition 来表示：

```java
   AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext();
    GenericBeanDefinition genericBeanDefinition = new GenericBeanDefinition();
    genericBeanDefinition.setBeanClass(AuthorService.class);
    genericBeanDefinition.setScope(BeanDefinition.SCOPE_PROTOTYPE);
    context.registerBeanDefinition("authorService", genericBeanDefinition);
    context.refresh();
    BeanDefinition mergedBeanDefinition = context.getBeanFactory().getMergedBeanDefinition("authorService");
    BeanDefinition beanDefinition = context.getBeanFactory().getMergedBeanDefinition("authorService");
    System.out.println(mergedBeanDefinition);
    System.out.println(beanDefinition);
```

运行结果：

```shell
Root bean: class [com.codebear.springcycle.AuthorService]; scope=prototype; abstract=false; lazyInit=false; autowireMode=0; dependencyCheck=0; autowireCandidate=true; primary=false; factoryBeanName=null; factoryMethodName=null; initMethodName=null; destroyMethodName=null
Root bean: class [com.codebear.springcycle.AuthorService]; scope=prototype; abstract=false; lazyInit=false; autowireMode=0; dependencyCheck=0; autowireCandidate=true; primary=false; factoryBeanName=null; factoryMethodName=null; initMethodName=null; destroyMethodName=null
```

可以看到，当没有父子关系，beanDefinition 依旧会被保存在 mergedBeanDefinitions 中，只是存储的内容和 beanDefinitions 中所存储的内容是一模一样的。

##### GenericBeanDefinition 总结

GenericBeanDefinition 替代了低版本 Spring 的 ChildBeanDefinition，GenericBeanDefinition 比 ChildBeanDefinition、RootBeanDefinition 更加灵活，既可以单独作为 BeanDefinition，也可以作为父 BeanDefinition，还可以作为子 GenericBeanDefinition。

#### RootBeanDefinition

在介绍 GenericBeanDefinition 的时候，写了两段代码。

给第一个代码打上断点，观察下 mergedBeanDefinitions，会发现 parentBeanDefinition 和 childBeanDefinition 在 mergedBeanDefinitions 都变为了 RootBeanDefinition： ![image.png](../assets/15100432-bef9e1704c952ffe.png)

给第二个代码打上断点，也观察下 mergedBeanDefinitions，会发现 authorService 在 mergedBeanDefinitions 也变为了 RootBeanDefinition： ![image.png](../assets/15100432-d355a3707f7a6a85.png)

可以看到在 mergedBeanDefinitions 存放的都是 RootBeanDefinition。

RootBeanDefinition 也可以用来充当父 BeanDefinition，就像下面的酱紫：

```java
 public static void main(String[] args) {
        AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext();
        RootBeanDefinition genericBeanDefinition = new RootBeanDefinition();
        genericBeanDefinition.setBeanClass(ParentService.class);
        genericBeanDefinition.setScope(BeanDefinition.SCOPE_PROTOTYPE);
        context.registerBeanDefinition("parent", genericBeanDefinition);
        GenericBeanDefinition rootBeanDefinition = new GenericBeanDefinition();
        rootBeanDefinition.setBeanClass(ChildService.class);
        rootBeanDefinition.setParentName("parent");
        context.refresh();
    }
```

但是 RootBeanDefinition 不可以充当子 BeanDefinition：

```java
  public static void main(String[] args) {
        AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext();
        RootBeanDefinition genericBeanDefinition = new RootBeanDefinition();
        genericBeanDefinition.setBeanClass(ParentService.class);
        genericBeanDefinition.setScope(BeanDefinition.SCOPE_PROTOTYPE);
        context.registerBeanDefinition("parent", genericBeanDefinition);
        RootBeanDefinition rootBeanDefinition = new RootBeanDefinition();
        rootBeanDefinition.setBeanClass(ChildService.class);
        rootBeanDefinition.setParentName("parent");
        context.refresh();
    }
```

运行结果：

```java
Exception in thread "main" java.lang.IllegalArgumentException: Root bean cannot be changed into a child bean with parent reference
 at org.springframework.beans.factory.support.RootBeanDefinition.setParentName(RootBeanDefinition.java:260)
 at com.codebear.springcycle.Main.main(Main.java:20)
```

抛出了异常。

查询源码：

```java
 @Override
 public void setParentName(@Nullable String parentName) {
  if (parentName != null) {
   throw new IllegalArgumentException("Root bean cannot be changed into a child bean with parent reference");
  }
 }
```

发现调用 RootBeanDefinition 的 setParentName 方法，直接抛出了异常。

##### RootBeanDefinition 总结

RootBeanDefinition 可以作为其他 BeanDefinition 的父 BeanDefinition，也可以单独作为 BeanDefinition，但是不能作为其他 BeanDefinition 的子 BeanDefinition，在 mergedBeanDefinitions 存储的都是 RootBeanDefinition。

### ScannedGenericBeanDefinition

```java
@Configuration
@ComponentScan
public class AppConfig {
}
@Service
public class AuthorService {
}
public class Main {
    public static void main(String[] args) {
        AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext(AppConfig.class);
        System.out.println(context.getBeanDefinition("authorService").getClass());
    }
}
```

运行结果：

```plaintext
class org.springframework.context.annotation.ScannedGenericBeanDefinition
```

通过注解扫描出来的 Bean 的 BeanDefinition 用 ScannedGenericBeanDefinition 来表示。

### AnnotatedGenericBeanDefinition

```java
 public static void main(String[] args) {
        AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext(AppConfig.class);
        System.out.println(context.getBeanDefinition("appConfig").getClass());
    }
```

运行结果：

```plaintext
class org.springframework.beans.factory.annotation.AnnotatedGenericBeanDefinition
```

配置类的 BeanDefinition 用 AnnotatedGenericBeanDefinition 来表示。

### ConfigurationClassBeanDefinition

```java
public class AuthorService {
}
@Configuration
@ComponentScan
public class AppConfig {
    @Bean
    public AuthorService authorService() {
        return null;
    }
}
    public static void main(String[] args) {
        AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext(AppConfig.class);
 System.out.println(context.getBeanDefinition("authorService").getClass());
    }
```

运行结果：

```plaintext
  class org.springframework.context.annotation.ConfigurationClassBeanDefinitionReader$ConfigurationClassBeanDefinition
```

用@Bean 声明的 Bean 的 BeanDefinition 用 ConfigurationClassBeanDefinition 来表示。

是不是完全没想到，一个 BeanDefinition 可以牵涉到这么多的内容，这些内容说没用，确实没什么用；说有用，也有用。不明白这些内容，阅读 Spring 源码会比较懵逼，为什么会有那么多的 BeanDefinition。这个时候，你就会卡壳，拼命的想弄懂这些 BeanDefinition 都是用来干嘛的，但是网上关于 BeanDefinition 的博客不算太多，比较好的博客就更少了，希望此篇文章可以填充这块空白。
