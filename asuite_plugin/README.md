# **Asuite IntelliJ plugin**

## **Development**

#### How to build/install the plugin

**Build:** `$./gradlew jar`

The artifact will be generated at build/libs/asuite_plugin.jar.

**Install:**  Place the asuite_plugin.jar into the IntelliJ/config/plugins
 directory. The typical path of IntelliJ is /opt/intellij.

**Debug in IntelliJ:** Edit configurations -> add Gradle -> fill

gradle project:`asuite_plugin`

Tasks: `:runIde`

#### Quick start

1. Click Atest button, the Atest tool window shall show up.
2. Fill in the test module.
    * Enter a target module, e.g. aidegen_unittests.
    * Or fill target path with check test_mapping checkbox, E.g.
    tools/tradefederation/core.
3. Click Run, the test result will be shown in Atest tool window.

