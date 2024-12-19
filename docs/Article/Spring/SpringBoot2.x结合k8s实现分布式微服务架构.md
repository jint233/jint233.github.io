# Spring Boot 2.x 结合 k8s 实现分布式微服务架构

### Spring Boot 1.x 与 2.x 的区别

在《[微服务 Spring Cloud 架构设计](https://gitbook.cn/gitchat/activity/5e8ada3452383e517ff2b5f8)》一文中，笔者讲过 Spring Cloud 的架构设计。其实 Spring Boot 在一开始时，运用到的基本就是 Eureka、Config、Zuul、Ribbon、Feign、Hystrix 等。到了 Spring Boot 2.x 的时候，大量的组件开始风云崛起。下面简单列下这两个版本之间的区别如下。

Spring Boot 1.x 中，session 的超时时间是这样的：

```plaintext
server.session.timeout=3600
```

而在 2.x 中：

```plaintext
server.servlet.session.timeout=PT120M
```

截然不同的写法，cookie 也是一样的：

```plaintext
server:
  servlet:
    session:
      timeout: PT120M
      cookie:
        name: ORDER-SERVICE-SESSIONID
```

- 应用的 ContextPath 配置属性改动，跟上面的 session 一样，加上了一个 servlet。
- Spring Boot 2.x 基于 Spring 5，而 Spring Boot 1.x 基于 Spring 4 或较低。
- 统一错误处理的基类 AbstarctErrorController 的改动。
- 配置文件的中文可以直接读取，不需要转码。
- Acutator 变化很大，默认情况不再启用所有监控，需要定制化编写监控信息，完全需要重写，HealthIndicator,EndPoint 同理。
- 从 Spring Boot 2.x 开始，可以与 K8s 结合来实现服务的配置管理、负载均衡等，这是与 1.x 所不同的。

### K8s 的一些资源的介绍

上面说到 Spring Boot 2.x 可以结合 K8s 来作为微服务的架构设计，那么就先来说下 K8s 的一些组件吧。

ConfigMap，看到这个名字可以理解：它是用于保存配置信息的键值对，可以用来保存单个属性，也可以保存配置文件。对于一些非敏感的信息，比如应用的配置信息，则可以使用 ConfigMap。

创建一个 ConfigMap 有多种方式如下。

**1. key-value 字符串创建** 

```plaintext
kubectl create configmap test-config --from-literal=baseDir=/usr
```

上面的命令创建了一个名为 test-config，拥有一条 key 为 baseDir，value 为 "/usr" 的键值对数据。 **2. 根据 yml 描述文件创建** 

```plaintext
apiVersion: v1

kind: ConfigMap

metadata:

name: test-config

data:

baseDir: /usr
```

也可以这样，创建一个 yml 文件，选择不同的环境配置不同的信息：

```plaintext
kind: ConfigMap

apiVersion: v1

metadata:

name: cas-server

data:

application.yaml: |-
```

greeting:
  message: Say Hello to the World
---
spring:
  profiles: dev
greeting:
  message: Say Hello to the Dev
spring:
  profiles: test
greeting:
  message: Say Hello to the Test
spring:
  profiles: prod
greeting:
  message: Say Hello to the Prod

```plaintext
```
注意点：
1.  ConfigMap 必须在 Pod 使用其之前创建。
2.  Pod 只能使用同一个命名空间的 ConfigMap。
当然，还有其他更多用途，具体可以参考官网。
Service，顾名思义是一个服务，什么样的服务呢？它是定义了一个服务的多种 pod 的逻辑合集以及一种访问 pod 的策略。
service 的类型有四种：
*   ExternalName：创建一个 DNS 别名指向 service name，这样可以防止 service name 发生变化，但需要配合 DNS 插件使用。
*   ClusterIP：默认的类型，用于为集群内 Pod 访问时，提供的固定访问地址,默认是自动分配地址,可使用 ClusterIP 关键字指定固定 IP。
*   NodePort：基于 ClusterIp，用于为集群外部访问 Service 后面 Pod 提供访问接入端口。
*   LoadBalancer：它是基于 NodePort。
### 如何使用 K8s 来实现服务注册与发现
从上面讲的 Service，我们可以看到一种场景：所有的微服务在一个局域网内，或者说在一个 K8s 集群下，那么可以通过 Service 用于集群内 Pod 的访问，这就是 Service 默认的一种类型 ClusterIP，ClusterIP 这种的默认会自动分配地址。
那么问题来了，既然可以通过上面的 ClusterIp 来实现集群内部的服务访问，那么如何注册服务呢？其实 K8s 并没有引入任何的注册中心，使用的就是 K8s 的 kube-dns 组件。然后 K8s 将 Service 的名称当做域名注册到 kube-dns 中，通过 Service 的名称就可以访问其提供的服务。那么问题又来了，如果一个服务的 pod 对应有多个，那么如何实现 LB？其实，最终通过 kube-proxy，实现负载均衡。
说到这，我们来看下 Service 的服务发现与负载均衡的策略，Service 负载分发策略有两种：
*   RoundRobin：轮询模式，即轮询将请求转发到后端的各个 pod 上，其为默认模式。
*   SessionAffinity：基于客户端 IP 地址进行会话保持的模式，类似 IP Hash 的方式，来实现服务的负载均衡。
其实，K8s 利用其 Service 实现服务的发现，其实说白了，就是通过域名进行层层解析，最后解析到容器内部的 ip 和 port 来找到对应的服务，以完成请求。
下面写一个很简单的例子：
```

apiVersion: v1

kind: Service

metadata:

name: cas-server-service

namespace: default

spec:

ports:

- name: cas-server01

  port: 2000

  targetPort: cas-server01

  selector:

  app: cas-server

```plaintext
可以看到执行 `kubectl apply -f service.yaml` 后：
```

\[email protected\]:~$ kubectl get svc

NAME                          TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)              AGE

admin-web-service             ClusterIP   10.16.129.24    <none>        2001/TCP              84d

cas-server-service            ClusterIP   10.16.230.167   <none>        2000/TCP               67d

cloud-admin-service-service   ClusterIP   10.16.25.178    <none>        1001/TCP         190d

```plaintext
这样，我们可以看到默认的类型是 ClusterIP，用于为集群内 Pod 访问时，可以先通过域名来解析到多个服务地址信息，然后再通过 LB 策略来选择其中一个作为请求的对象。
### K8s 如何来处理微服务中常用的配置
在上面，我们讲过了几种创建 ConfigMap 的方式，其中有一种在 Java 中常常用到：通过创建 yml 文件来实现配置管理。
比如：
```

kind: ConfigMap

apiVersion: v1

metadata:

name: cas-server

data:

application.yaml: |-

```plaintext
greeting:
  message: Say Hello to the World
---
spring:
  profiles: dev
greeting:
  message: Say Hello to the Dev
spring:
  profiles: test
greeting:
  message: Say Hello to the Test
spring:
  profiles: prod
greeting:
  message: Say Hello to the Prod
```



```plaintext
上面创建了一个 yml 文件，同时，通过 spring.profiles 指定了开发、测试、生产等每种环境的配置。
具体代码：
```

apiVersion: apps/v1

kind: Deployment

metadata:

name: cas-server-deployment

labels:

```plaintext
app: cas-server
```

spec:

replicas: 1

selector:

```plaintext
matchLabels:
  app: cas-server
```

template:

```java
metadata:
  labels:
    app: cas-server
spec:
  nodeSelector:
    cas-server: "true"
  containers:
  - name: cas-server
    image: {{ cluster_cfg['cluster']['docker-registry']['prefix'] }}cas-server
    imagePullPolicy: Always
    ports:
      - name: cas-server01
        containerPort: 2000
    volumeMounts:
    - mountPath: /home/cas-server
      name: cas-server-path
    args: ["sh", "-c", "nohup java $JAVA_OPTS -jar -XX:MetaspaceSize=128m -XX:MaxMetaspaceSize=128m -Xms1024m -Xmx1024m -Xmn256m -Xss256k -XX:SurvivorRatio=8 -XX:+UseConcMarkSweepGC cas-server.jar --spring.profiles.active=dev", "&"]
  hostAliases:
  - ip: "127.0.0.1"
    hostnames:
    - "gemantic.localhost"
  - ip: "0.0.0.0"
    hostnames:
    - "gemantic.all"
  volumes:
  - name: cas-server-path
    hostPath:
      path: /var/pai/cas-server
```



```plaintext
这样，当我们启动容器时，通过 `--spring.profiles.active=dev` 来指定当前容器的活跃环境，即可获取 ConfigMap 中对应的配置。是不是感觉跟 Java 中的 Config 配置多个环境的配置有点类似呢？但是，我们不用那么复杂，这些统统可以交给 K8s 来处理。只需要你启动这一命令即可，是不是很简单？
### Spring Boot 2.x 的新特性
在第一节中，我们就讲到 1.x 与 2.x 的区别，其中最为凸显的是，Spring Boot 2.x 结合了 K8s 来实现微服务的架构设计。其实，在 K8s 中，更新 ConfigMap 后，pod 是不会自动刷新 configMap 中的变更，如果想要获取 ConfigMap 中最新的信息，需要重启 pod。
但 2.x 提供了自动刷新的功能：
```

spring:

application:

```plaintext
name: cas-server
```

cloud:

```plaintext
kubernetes:
  config:
    sources:
     - name: ${spring.application.name}
       namespace: default
  discovery:
    all-namespaces: true
  reload:
    enabled: true
    mode: polling
    period: 500
```



```plaintext
如上，我们打开了自动更新配置的开关，并且设置了自动更新的方式为主动拉取，时间间隔为 500ms，同时，还提供了另外一种方式——event 事件通知模式。这样，在 ConfigMap 发生改变时，无需重启 pod 即可获取最新的数据信息。
同时，Spring Boot 2.x 结合了 K8s 来实现微服务的服务注册与发现：
```

<dependency>

<groupId>org.springframework.cloud</groupId>

<artifactId>spring-cloud-kubernetes-core</artifactId>

</dependency>
<dependency>

<groupId>org.springframework.cloud</groupId>

<artifactId>spring-cloud-kubernetes-discovery</artifactId>

</dependency>

```plaintext
开启服务发现功能：
```

spring:

cloud:

```plaintext
kubernetes:
  discovery:
    all-namespaces: true
```



```plaintext
开启后，我们在《\[微服务 Spring Cloud 架构设计\]》一文中讲过，其实最终是向 K8s 的 API Server 发起 http 请求，获取 Service 资源的数据列表。然后根据底层的负载均衡策略来实现服务的发现，最终解析到某个 pod 上。那么为了同一服务的多个 pod 存在，我们需要执行：
```

kubectl scale --replicas=2 deployment admin-web-deployment

```plaintext
同时，我们如果通过 HTTP 的 RestTemplate Client 来作服务请求时，可以配置一些请求的策略，RestTemplate 一般与 Ribbon 结合使用：
```

client:

http:

```plaintext
request:
  connectTimeout: 8000
  readTimeout: 3000
```

backend:

ribbon:

```plaintext
eureka:
  enabled: false
client:
  enabled: true
ServerListRefreshInterval: 5000
```

ribbon:

ConnectTimeout: 8000

ReadTimeout: 3000

eager-load:

```plaintext
enabled: true
clients: cas-server-service,admin-web-service
```

MaxAutoRetries: 1 #对第一次请求的服务的重试次数

MaxAutoRetriesNextServer: 1 #要重试的下一个服务的最大数量（不包括第一个服务）

# ServerListRefreshInterval: 2000

OkToRetryOnAllOperations: true

NFLoadBalancerRuleClassName: com.netflix.loadbalancer.RoundRobinRule #com.damon.config.RibbonConfiguration #分布式负载均衡策略

```plaintext
可以配置一些服务列表，自定义一些负载均衡的策略。
如果你是使用 Feign 来作为 LB，其实与 Ribbon 只有一点点不一样，因为 Feign 本身是基于 Ribbon 来实现的，除了加上注解 @EnableFeignClients 后，还要配置：
```

feign:

client:

```plaintext
config:
  default: #provider-service
    connectTimeout: 8000 #客户端连接超时时间
    readTimeout: 3000 #客户端读超时设置
    loggerLevel: full
```



```plaintext
其他的可以自定义负载均衡策略，这一点是基于 Ribbon 的，所以是一样的。
### 实战 Spring Boot 2.x 结合 K8s 来实现微服务架构设计
微服务架构中，主要的就是服务消费者、服务的生产者可以互通，可以发生调用，在这基础上，还可以实现负载均衡，即一个服务调用另一个服务时，在该服务存在多个节点的情况下，可以通过一些策略来找到该服务的一个合适的节点访问。下面主要介绍服务的生产者与消费者。
先看生产者，引入常用的依赖：
```

<parent>

```java
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>2.1.13.RELEASE</version>
    <relativePath/>
</parent>
<properties>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <project.reporting.outputEncoding>UTF-8</project.reporting.outputEncoding>
    <java.version>1.8</java.version>
    <swagger.version>2.6.1</swagger.version>
    <xstream.version>1.4.7</xstream.version>
    <pageHelper.version>4.1.6</pageHelper.version>
    <fastjson.version>1.2.51</fastjson.version>
    <springcloud.version>Greenwich.SR3</springcloud.version>
    <springcloud.kubernetes.version>1.1.1.RELEASE</springcloud.kubernetes.version>
    <mysql.version>5.1.46</mysql.version>
</properties>
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-dependencies</artifactId>
            <version>${springcloud.version}</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>
```

<dependencies>

```java
      <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
        <exclusions>
            <exclusion>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-starter-tomcat</artifactId>
            </exclusion>
        </exclusions>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-undertow</artifactId>
    </dependency>
<!-- 配置加载依赖 -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-actuator</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-actuator-autoconfigure</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.cloud</groupId>
        <artifactId>spring-cloud-starter-kubernetes-config</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-test</artifactId>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>io.jsonwebtoken</groupId>
        <artifactId>jjwt</artifactId>
        <version>0.9.0</version>
    </dependency>
    <dependency>
        <groupId>cn.hutool</groupId>
        <artifactId>hutool-all</artifactId>
        <version>4.6.3</version>
    </dependency>
    <dependency>
        <groupId>com.google.guava</groupId>
        <artifactId>guava</artifactId>
        <version>19.0</version>
    </dependency>
    <dependency>
        <groupId>org.apache.commons</groupId>
        <artifactId>commons-lang3</artifactId>
        </dependency>
    <dependency>
        <groupId>commons-collections</groupId>
        <artifactId>commons-collections</artifactId>
        <version>3.2.2</version>
    </dependency>
    <dependency>
        <groupId>io.springfox</groupId>
        <artifactId>springfox-swagger2</artifactId>
        <version>${swagger.version}</version>
    </dependency>
    <dependency>
        <groupId>io.springfox</groupId>
        <artifactId>springfox-swagger-ui</artifactId>
        <version>${swagger.version}</version>
    </dependency>
<!-- 数据库分页依赖 -->
    <dependency>
      <groupId>com.github.pagehelper</groupId>
      <artifactId>pagehelper</artifactId>
      <version>${pageHelper.version}</version>
    </dependency>
    <dependency>
        <groupId>org.mybatis.spring.boot</groupId>
        <artifactId>mybatis-spring-boot-starter</artifactId>
        <version>1.1.1</version>
    </dependency>
    <dependency>
        <groupId>mysql</groupId>
        <artifactId>mysql-connector-java</artifactId>
        <version>${mysql.version}</version>
    </dependency>
<!-- 数据库驱动 -->
    <dependency>
        <groupId>com.alibaba</groupId>
        <artifactId>druid</artifactId>
        <version>1.1.3</version>
    </dependency>
    <dependency>
        <groupId>com.alibaba</groupId>
        <artifactId>fastjson</artifactId>
        <version>${fastjson.version}</version>
    </dependency>
    <dependency>
      <groupId>org.jsoup</groupId>
      <artifactId>jsoup</artifactId>
      <version>1.11.3</version>
    </dependency>
</dependencies>
```



```plaintext
上面我们使用了比较新的版本：Spring Boot 2.1.13，Cloud 版本是 Greenwich.SR3，其次，我们配置了 K8s 的 ConfigMap 所用的依赖，加上了数据库的一些配置，具体其他的，实现过程中，大家可以自行添加。
接下来，我们看启动时加载的配置文件，这里加了关于 K8s ConfigMap 所管理的配置所在的信息，以及保证服务被发现，开启了所有的 namespace，同时还启动了配置自动刷新的功能，注意的是，该配置需要在 bootstrap 文件：
```

spring:

application:

```plaintext
name: cas-server
```

cloud:

```plaintext
kubernetes:
  config:
    sources:
     - name: ${spring.application.name}
       namespace: default
  discovery:
    all-namespaces: true #发现所有的命令空间的服务
  reload:
    enabled: true
    mode: polling #自动刷新模式为拉取模式，也可以是事件模式 event
    period: 500 #拉取模式下的频率
```

logging: #日志路径设置

path: /data/${spring.application.name}/logs

```plaintext
剩下的一些配置可以在 application 文件中配置：
```

spring:

profiles:

```plaintext
active: dev
```

server:

port: 2000

undertow:

```plaintext
accesslog:
  enabled: false
  pattern: combined
```

servlet:

```plaintext
session:
  timeout: PT120M #session 超时时间
```

client:

http:

```plaintext
request:
  connectTimeout: 8000
  readTimeout: 30000
```

mybatis: #持久层配置

mapperLocations: classpath:mapper/\*.xml

typeAliasesPackage: com.damon.\*.model

```plaintext
接下来看下启动类：
```

/**

-

- @author Damon

- @date 2020 年 1 月 13 日 下午 8:29:42

-

\*/

@Configuration

@EnableAutoConfiguration

@ComponentScan(basePackages = {"com.damon"})

//@SpringBootApplication(scanBasePackages = { "com.damon" })

@EnableConfigurationProperties(EnvConfig.class)

public class CasApp {

```java
public static void main(String[] args) {
    SpringApplication.run(CasApp.class, args);
}
```

}

```plaintext
这里我们没有直接用注解 @SpringBootApplication，因为主要用到的就是几个配置，没必要全部加载。
我们看到启动类中有一个引入的 EnvConfig.class：
```

/**

- @author Damon

- @date 2019 年 10 月 25 日 下午 8:54:01

-

\*/
@Configuration

@ConfigurationProperties(prefix = "greeting")

public class EnvConfig {
private String message = "This is a dummy message";
public String getMessage() {

```java
    return this.message;
}
public void setMessage(String message) {
    this.message = message;
}
```



```plaintext
这就是配置 ConfigMap 中的属性的类。剩下的可以自己定义一个接口类，来实现服务生产者。
最后，我们需要在 K8s 下部署的话，需要准备几个脚本。 **1. 创建 ConfigMap** ```
kind: ConfigMap

apiVersion: v1

metadata:

  name: cas-server

data:

  application.yaml: |-

    greeting:

      message: Say Hello to the World

    ---

    spring:

      profiles: dev

    greeting:

      message: Say Hello to the Dev

    spring:

      profiles: test

    greeting:

      message: Say Hello to the Test

    spring:

      profiles: prod

    greeting:

      message: Say Hello to the Prod
```

设置了不同环境的配置，注意，这里的 namespace 需要与服务部署的 namespace 一致，这里默认的是 default，而且在创建服务之前，先得创建这个。 **2. 创建服务部署脚本** 

```plaintext
apiVersion: apps/v1
kind: Deployment
metadata:
name: cas-server-deployment
labels:
```

app: cas-server

```plaintext
spec:
replicas: 3
selector:
```

matchLabels:

  app: cas-server

```plaintext
template:
```

metadata:

  labels:

    app: cas-server

spec:

  nodeSelector:

    cas-server: "true"

  containers:

  - name: cas-server

    image: cas-server

    imagePullPolicy: Always

    ports:

      - name: cas-server01

        containerPort: 2000

    volumeMounts:

    - mountPath: /home/cas-server

      name: cas-server-path

    - mountPath: /data/cas-server

      name: cas-server-log-path

    - mountPath: /etc/kubernetes

      name: kube-config-path

    args: ["sh", "-c", "nohup java JAVA_OPTS -jar -XX:MetaspaceSize=128m -XX:MaxMetaspaceSize=128m -Xms1024m -Xmx1024m -Xmn256m -Xss256k -XX:SurvivorRatio=8 -XX:+UseConcMarkSweepGC cas-server.jar --spring.profiles.active=dev", "&"]

  volumes:

  - name: cas-server-path

    hostPath:

      path: /var/pai/cas-server

  - name: cas-server-log-path

    hostPath:

      path: /data/cas-server

  - name: kube-config-path

    hostPath:

      path: /etc/kubernetes

```plaintext
```

注意：这里有个属性 replicas，其作用是当前 pod 所启动的副本数，即我们常说的启动的节点个数，当然，你也可以通过前面讲的脚本来执行生成多个 pod 副本。如果这里没有设置多个的话，也可以通过命令来执行：
```

kubectl scale --replicas=3 deployment cas-server-deployment

```plaintext
这里，我建议使用 Deployment 类型的来创建 pod，因为 Deployment 类型更好的支持弹性伸缩与滚动更新。

同时，我们通过 `--spring.profiles.active=dev` 来指定当前 pod 的运行环境。 **3. 创建一个 Service**

最后，如果服务想被发现，需要创建一个 Service：
```

apiVersion: v1
kind: Service
metadata:
name: cas-server-service
namespace: default
spec:
ports:

- name: cas-server01
  port: 2000
  targetPort: cas-server01
  selector:
  app: cas-server

```plaintext
注意，这里的 namespace 需要与服务部署的 namespace 一致，这里默认的是 default。

看看服务的消费者，同样，先看引入常用的依赖：
```

<parent>

```plaintext
    <groupId>org.springframework.boot</groupId>
```

<artifactId>spring-boot-starter-parent</artifactId>

<version>2.1.13.RELEASE</version>

<relativePath/>

```plaintext
</parent>
<properties>
```

<project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>

<project.reporting.outputEncoding>UTF-8</project.reporting.outputEncoding>

<java.version>1.8</java.version>

<swagger.version>2.6.1</swagger.version>

<xstream.version>1.4.7</xstream.version>

<pageHelper.version>4.1.6</pageHelper.version>

<fastjson.version>1.2.51</fastjson.version>

<springcloud.version>Greenwich.SR3</springcloud.version>

<!-- <springcloud.version>2.1.8.RELEASE</springcloud.version> -->

<springcloud.kubernetes.version>1.1.1.RELEASE</springcloud.kubernetes.version>

<mysql.version>5.1.46</mysql.version>

```plaintext
</properties>
<dependencyManagement>
```

<dependencies>

    <dependency>

        <groupId>org.springframework.cloud</groupId>

        <artifactId>spring-cloud-dependencies</artifactId>

        <version>${springcloud.version}</version>

        <type>pom</type>

        <scope>import</scope>

    </dependency>

</dependencies>

```plaintext
</dependencyManagement>
<dependencies>
```

<dependency>

    <groupId>org.springframework.boot</groupId>

    <artifactId>spring-boot-starter-web</artifactId>

    <exclusions>

        <exclusion>

            <groupId>org.springframework.boot</groupId>

            <artifactId>spring-boot-starter-tomcat</artifactId>

        </exclusion>

    </exclusions>

</dependency>

<dependency>

    <groupId>org.springframework.boot</groupId>

    <artifactId>spring-boot-starter-undertow</artifactId>

</dependency>
<dependency>

    <groupId>org.springframework.boot</groupId>

    <artifactId>spring-boot-starter-test</artifactId>

    <scope>test</scope>

</dependency>

```plaintext
```
<!-- 配置加载依赖 -->
```



```plaintext
<dependency>

    <groupId>org.springframework.boot</groupId>

    <artifactId>spring-boot-actuator</artifactId>

</dependency>
<dependency>

    <groupId>org.springframework.boot</groupId>

    <artifactId>spring-boot-actuator-autoconfigure</artifactId>

</dependency>
<dependency>

    <groupId>org.springframework.cloud</groupId>

    <artifactId>spring-cloud-starter-kubernetes-config</artifactId>

    </dependency>
<dependency>

    <groupId>org.springframework.cloud</groupId>

    <artifactId>spring-cloud-commons</artifactId>

</dependency>
```

<!-- 结合 k8s 实现服务发现 -->

```plaintext
<dependency>

    <groupId>org.springframework.cloud</groupId>

    <artifactId>spring-cloud-kubernetes-core</artifactId>

</dependency>
<dependency>

    <groupId>org.springframework.cloud</groupId>

    <artifactId>spring-cloud-kubernetes-discovery</artifactId>

</dependency>
```

<!-- 负载均衡策略 -->

```plaintext
<dependency>

    <groupId>org.springframework.cloud</groupId>

    <artifactId>spring-cloud-starter-kubernetes-ribbon</artifactId>

</dependency>
<dependency>

    <groupId>org.springframework.cloud</groupId>

    <artifactId>spring-cloud-starter-netflix-ribbon</artifactId>

</dependency>
```

<!-- 熔断机制 -->

```java
<dependency>

    <groupId>org.springframework.cloud</groupId>

    <artifactId>spring-cloud-starter-netflix-hystrix</artifactId>

</dependency>
<dependency>

    <groupId>cn.hutool</groupId>

    <artifactId>hutool-all</artifactId>

    <version>4.6.3</version>

</dependency>
<dependency>

    <groupId>com.alibaba</groupId>

    <artifactId>fastjson</artifactId>

    <version>${fastjson.version}</version>

</dependency>
<dependency>

  <groupId>org.jsoup</groupId>

  <artifactId>jsoup</artifactId>

  <version>1.11.3</version>

</dependency>
<dependency>

    <groupId>io.springfox</groupId>

    <artifactId>springfox-swagger2</artifactId>

    <version>${swagger.version}</version>

</dependency>

<dependency>

    <groupId>io.springfox</groupId>

    <artifactId>springfox-swagger-ui</artifactId>

    <version>${swagger.version}</version>

</dependency>
<dependency>

    <groupId>org.apache.commons</groupId>

    <artifactId>commons-lang3</artifactId>

    </dependency>
<dependency>

    <groupId>commons-collections</groupId>

    <artifactId>commons-collections</artifactId>

    <version>3.2.2</version>

</dependency>
<!-- 数据库分页 -->

<dependency>

  <groupId>com.github.pagehelper</groupId>

  <artifactId>pagehelper</artifactId>

  <version>${pageHelper.version}</version>

</dependency>
<dependency>

    <groupId>org.mybatis.spring.boot</groupId>

    <artifactId>mybatis-spring-boot-starter</artifactId>

    <version>1.1.1</version>

</dependency>
<dependency>

    <groupId>mysql</groupId>

    <artifactId>mysql-connector-java</artifactId>

    <version>${mysql.version}</version>

</dependency>
```

<!-- 数据库驱动 -->

```plaintext
<dependency>

    <groupId>com.alibaba</groupId>

    <artifactId>druid</artifactId>

    <version>1.1.3</version>

</dependency>
```

</dependencies>

```plaintext
```

这里大部分的依赖跟生产者一样，但，需要加入服务发现的依赖，以及所用的负载均衡的策略依赖、服务的熔断机制。

接下来 bootstrap 文件中的配置跟生产者一样，这里不在说了，唯一不同的是 application 文件：
```

backend:
ribbon:

```plaintext
eureka:

enabled: false

client:

enabled: true

ServerListRefreshInterval: 5000
```

ribbon:
ConnectTimeout: 3000
ReadTimeout: 1000
eager-load:

```plaintext
enabled: true

clients: cas-server-service,edge-cas-service,admin-web-service #负载均衡发现的服务列表
```

MaxAutoRetries: 1 #对第一次请求的服务的重试次数
MaxAutoRetriesNextServer: 1 #要重试的下一个服务的最大数量（不包括第一个服务）
OkToRetryOnAllOperations: true
NFLoadBalancerRuleClassName: com.netflix.loadbalancer.RoundRobinRule #负载均衡策略
hystrix:
command:

```plaintext
BackendCall:

execution:
```

isolation:

  thread:

    timeoutInMilliseconds: 5000 #熔断机制设置的超时时间

```plaintext
```
threadpool:
```

BackendCallThread:

coreSize: 5

```plaintext
```

引入了负载均衡的机制以及策略（可以自定义策略）。

接下来看启动类：
```

/**
- @author Damon
- @date 2020 年 1 月 13 日 下午 9:23:06
-
\*/
@Configuration
@EnableAutoConfiguration
@ComponentScan(basePackages = {"com.damon"})
@EnableConfigurationProperties(EnvConfig.class)
@EnableDiscoveryClient
public class AdminApp {
public static void main(String\[\] args) {

```bash
```
SpringApplication.run(AdminApp.class, args);
```

}

```plaintext
}
```

同样的 EnvConfig 类，这里不再展示了。其他的比如：注解 @EnableDiscoveryClient 是为了服务发现。

同样，我们新建接口，假如我们生产者有一个接口是：

```plaintext
<http://cas-server-service/api/getUser>
```

则，我们在调用它时，可以通过 RestTemplate Client 来直接调用，通过 Ribbon 来实现负载均衡：

```plaintext
@LoadBalanced
```

@Bean

public RestTemplate restTemplate() {

```java
SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();

requestFactory.setReadTimeout(env.getProperty("client.http.request.readTimeout", Integer.class, 15000));

requestFactory.setConnectTimeout(env.getProperty("client.http.request.connectTimeout", Integer.class, 3000));

RestTemplate rt = new RestTemplate(requestFactory);

return rt;
```

}

```plaintext
```

可以看到，这种方式的分布式负载均衡实现起来很简单，直接注入一个初始化 Bean，加上一个注解 @LoadBalanced 即可。

在实现类中，我们只要直接调用服务生产者：
```

java
ResponseEntity<String> forEntity = restTemplate.getForEntity("http://cas-server/api/getUser", String.class);

```plaintext
其中，URL 中 必须要加上 `"http://"`，这样即可实现服务的发现以及负载均衡，其中，LB 的策略，可以采用 Ribbon 的几种方式，也可以自定义一种。

最后，可以在实现类上加一个熔断机制：
```

java
@HystrixCommand(fallbackMethod = "admin_service_fallBack")
public Response<Object> getUserInfo(HttpServletRequest req, HttpServletResponse res) {
        ResponseEntity<String> forEntity = restTemplate.getForEntity(envConfig.getCas_server_url() + "/api/getUser", String.class);
        logger.info("test restTemplate.getForEntity(): {}", forEntity);
        if (forEntity.getStatusCodeValue() == 200) {
                logger.info("================================test restTemplate.getForEntity(): {}", JSON.toJSON(forEntity.getBody()));
                logger.info(JSON.toJSONString(forEntity.getBody()));
        }
}

```plaintext
其中发生熔断时，回调方法：
```

java
private Response<Object> admin_service_fallBack(HttpServletRequest req, HttpServletResponse res) {
        String token = StrUtil.subAfter(req.getHeader("Authorization"), "bearer ", false);
        logger.info("admin_service_fallBack token: {}", token);
        return Response.ok(200, -5, "服务挂啦!", null);
    }
```

其返回的对象必须与原函数一致，否则可能会报错。具体的可以参考《[Spring cloud 之熔断机制](https://mp.weixin.qq.com/s/TcwAONaCexKIeT-63ClGsg)》。

最后与生产者一样，需要创建 ConfigMap、Service、服务部署脚本，下面会开源这些代码，这里也就不一一展示了。最后，我们会发现：当请求 认证中心时，认证中心存在的多个 pod，可以被轮训的请求到。这就是基于 Ribbon 的轮训策略来实现分布式的负载均衡，并且基于 Redis 来实现信息共享。

### 结束福利

开源几个微服务的架构设计项目：

- [https://github.com/damon008/spring-cloud-oauth2](https://github.com/damon008/spring-cloud-oauth2)
- [https://github.com/damon008/spring-cloud-k8s](https://github.com/damon008/spring-cloud-k8s)
- [https://gitee.com/damon_one/spring-cloud-k8s](https://gitee.com/damon_one/spring-cloud-k8s)
- [https://gitee.com/damon_one/spring-cloud-oauth2](https://gitee.com/damon_one/spring-cloud-oauth2)

欢迎大家 star，多多指教。
