AIDEgen aims to automate the project setup process for developers to work on
Java project in Intellij. Developers no longer need to manually configure an
IntelliJ project, such as all the project dependencies. AIDEgen offers
the following features:

* Configures Intellij or Android Studio project files with indexing of
  API/Object references.

* Can be launched for a specified sub-project (V1), i.e. frameworks/base

* Can be launched for a specified module (V1), i.e. tradefed

* Integration with ASuite features to provide better user experience.

#1. Compilation:

    `$ make aidegen` # this produces aidegen in out/host/linux-x86/bin.

#2. Execution:

    `$ aidegen <project_path>` OR `$ aidegen <module>`
