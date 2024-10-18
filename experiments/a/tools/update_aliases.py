#!/usr/bin/env python3
#
# Copyright 2024 - The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Update Aliases."""

import inspect
import os
import sys
from core.errors import WorkflowError


class Alias:
  """Base class for defining an alias."""

  def build(self):
    return []

  def update(self):
    return []


class Core(Alias):
  """Alias for Core."""

  def build(self):
    return ['m framework framework-minus-apex']

  def update(self):
    return [
        'adevice update',
    ]


class SystemServer(Alias):
  """Alias for SystemServer."""

  def update(self):
    return [
        'adevice update --restart=none',
        'adb kill systemserver',
    ]


class SysUI(Alias):
  """Alias for SystemUI."""

  def build(self):
    if is_nexus():
      raise WorkflowError(
          "Target 'sysui' is not allowed on Nexus Experience devices.\n"
          'Try sysuig (with g at the end) or sysuititan'
      )
    return ['m framework framework-minus-apex SystemUI']

  def update(self):
    target = 'com.android.systemui'
    return [
        'adevice update --restart=none',
        f'adb shell "am force-stop {target}"',
    ]


class SysUIG(Alias):
  """Alias for SystemUI for Google Devices."""

  def build(self):
    if not is_nexus():
      raise WorkflowError(
          "Target 'sysuig' is only allowed on Nexus Experience devices.\n"
          'Try sysui (no g at the end)'
      )
    return ['m framework framework-minus-apex SystemUIGoogle']

  def update(self):
    target = 'com.android.systemui'
    return [
        'adevice update --restart=none',
        f'adb shell am force-stop {target}',
    ]


class SysUITitan(Alias):
  """Alias for SystemUI Titan devices."""

  def build(self):
    if not is_nexus():
      raise WorkflowError(
          "Target 'sysuititan' is only allowed on Nexus Experience devices.\n"
          'Try sysui (no g at the end)'
      )
    return ['m framework framework-minus-apex SystemUITitan']

  def update(self):
    target = 'com.android.systemui'
    return [
        'adevice update --restart=none',
        f'adb shell am force-stop {target}',
    ]


class SysUIGo(Alias):
  """Alias for SystemUI."""

  def build(self):
    if not is_nexus():
      raise WorkflowError(
          "Target 'sysuigo' is only allowed on Nexus Experience devices.\n"
          'Try sysui (no go at the end)'
      )
    return ['m framework framework-minus-apex SystemUIGo']

  def update(self):
    target = 'com.android.systemui'
    return [
        'adevice update --restart=none',
        f'adb shell am force-stop {target}',
    ]


class CarSysUI(Alias):
  """Alias for CarSystemUI."""

  def build(self):
    return ['m framework framework-minus-apex CarSystemUI']

  def update(self):
    target = 'com.android.systemui'
    return [
        'adevice update --restart=none',
        f'adb shell am force-stop {target}',
    ]


class CarSysUIG(Alias):
  """Alias for CarSystemUI."""

  def build(self):
    return ['m framework framework-minus-apex AAECarSystemUI']

  def update(self):
    target = 'com.android.systemui'
    return [
        'adevice update --restart=none',
        f'adb shell am force-stop {target}',
    ]


class Droid(Alias):
  """Alias for Droid."""

  def build(self):
    return ['m droid']

  def update(self):
    return ['flashall']


class Snod(Alias):
  """Alias for Snod."""

  def build(self):
    return ['m snod']

  def update(self):
    return ['flashall']


# These definitions are imported from makepush
# https://team.git.corp.google.com/android-framework/toolbox/+/refs/heads/main/makepush/makepush.sh
alias_definitions = {
    'core_jni': {'build': 'libandroid_runtime'},
    'res_jni': {'build': 'libandroidfw libidmap2'},
    'idmap2': {'build': 'idmap2 idmap2d'},
    'sf': {'build': 'surfaceflinger'},
    'res': {'build': 'framework-res'},
    'services': {'build': 'services protolog.conf.json.gz'},
    'inputflinger': {'build': 'libinputflinger'},
    'carsysui': {
        'build': 'carSystemUI',
        'update': 'adb shell am force-stop com.android.systemui',
    },
    'carsysuig': {
        'build': 'AAECarSystemUI',
        'update': 'adb shell am force-stop com.android.systemui',
    },
    'car-mainline': {
        'build': 'AAECarSystemUI',
        'update': (
            'adb install -r --staged --enable-rollback'
            ' $OUT/system/apex/com.android.car.framework.apex'
        ),
    },
    'carfwk': {'build': 'carfwk car-frameworks-service'},
    'carfwk-module': {'build': 'car-frameworks-service-module'},
    'carsettings': {
        'build': 'carSettings',
        'update': 'adb shell am force-stop com.android.car.settings',
    },
    'carks': {
        'build': 'EmbeddedKitchenSinkApp',
        'update': 'adb shell am force-stop com.google.android.car.kitchensink',
    },
    'carlauncher': {
        'build': 'carLauncher',
        'update': 'adb shell am force-stop com.android.car.carlauncher',
    },
    'carlauncherg': {
        'build': 'GASCarLauncher',
        'update': 'adb shell am force-stop com.android.car.carlauncher',
    },
    'car-md-launcher': {
        'build': 'MultiDisplaySecondaryHomeTestLauncher',
        'update': (
            'adb install'
            ' $OUT/system/priv-app/MultiDisplaySecondaryHomeTestLauncher/MultiDisplaySecondaryHomeTestLauncher.apk'
        ),
    },
    'carsuw': {
        'build': 'carProvision',
        'update': 'adb shell am force-stop com.android.car.provision',
    },
    'car': {'build': 'android.car'},
    'car-builtin': {'build': 'android.car.builtin'},
    'vhal-legacy': {
        'build': 'android.hardware.automotive.vehicle@2.0-service',
        'update': (
            'adb shell am force-stop'
            ' android.hardware.automotive.vehicle@2.0-service'
        ),
    },
    'vhal': {
        'build': 'android.hardware.automotive.vehicle@V1-default-service',
        'update': (
            'adb shell am force-stop'
            ' android.hardware.automotive.vehicle@V1-default-service'
        ),
    },
    'vhal-pasa': {
        'build': 'android.hardware.automotive.vehicle@V1-pasa-service',
        'update': (
            'adb shell am force-stop'
            ' android.hardware.automotive.vehicle@V1-pasa-service'
        ),
    },
    'launcher': {'build': 'NexusLauncherRelease'},
    'launcherd': {
        'build': 'nexusLauncherDebug',
        'update': (
            'adb install'
            ' $OUT/anywhere/priv-app/NexusLauncherDebug/NexusLauncherDebug.apk'
        ),
    },
    'launchergo': {
        'build': 'launcherGoGoogle',
        'update': 'adb shell am force-stop com.android.launcher3',
    },
    'intentresolver': {
        'build': 'intentResolver',
        'update': 'adb shell am force-stop com.android.intentresolver',
    },
    'sysuig': {
        'build': 'systemUIGoogle',
        'update': 'adb shell am force-stop com.android.systemui',
    },
    'sysuititan': {
        'build': 'systemUITitan',
        'update': 'adb shell am force-stop com.android.systemui',
    },
    'sysuigo': {
        'build': 'systemUIGo',
        'update': 'adb shell am force-stop com.android.systemui',
    },
    'flagflipper': {
        'build': 'theFlippinApp',
        'update': 'adb shell am force-stop com.android.theflippinapp',
    },
    'docsui': {
        'build': 'documentsUI',
        'update': 'adb shell am force-stop com.android.documentsui',
    },
    'docsuig': {
        'build': 'documentsUIGoogle',
        'update': 'adb shell am force-stop com.google.android.documentsui',
    },
    'settings': {
        'build': 'settings',
        'update': 'adb shell am force-stop com.android.settings',
    },
    'settingsg': {
        'build': 'SettingsGoogle',
        'update': 'adb shell am force-stop com.google.android.settings',
    },
    'settingsgf': {
        'build': 'SettingsGoogleFutureFaceEnroll',
        'update': (
            'adb shell am force-stop'
            ' com.google.android.settings.future.biometrics.faceenroll'
        ),
    },
    'settings_provider': {'build': 'SettingsProvider'},
    'apidemos': {
        'build': 'ApiDemos',
        'update': (
            'adb install'
            ' $OUT/testcases/ApiDemos/$var_cache_TARGET_ARCH/ApiDemos.apk'
        ),
    },
    'teleservice': {
        'build': 'TeleService',
        'update': 'adb shell am force-stop com.android.phone',
    },
    'managed_provisioning': {
        'build': 'ManagedProvisioning',
        'update': 'adb shell am force-stop com.android.managedprovisioning',
    },
    'car_managed_provisioning': {
        'build': 'carManagedProvisioning',
        'update': (
            'adb install'
            ' $OUT/anywhere/priv-app/CarManagedProvisioning/CarManagedProvisioning.apk'
        ),
    },
    'ctsv': {
        'build': 'ctsVerifier',
        'update': (
            'adb install'
            ' $OUT/testcases/CtsVerifier/$var_cache_TARGET_ARCH/CtsVerifier.apk'
        ),
    },
    'gtsv': {
        'build': 'gtsVerifier',
        'update': (
            'adb install'
            ' $OUT/testcases/GtsVerifier/$var_cache_TARGET_ARCH/GtsVerifier.apk'
        ),
    },
    'suw': {
        'build': 'Provision',
        'update': 'adb shell am force-stop com.android.provision',
    },
    'pkg_installer': {
        'build': 'PackageInstaller',
        'update': 'adb shell am force-stop com.android.packageinstaller',
    },
    'pkg_installer_g': {
        'build': 'GooglePackageInstaller',
        'update': 'adb shell am force-stop com.google.android.packageinstaller',
    },
    'perm_controller': {
        'build': 'PermissionController',
        'update': (
            'adb install'
            ' $OUT/apex/com.android.permission/priv-app/PermissionController/PermissionController.apk'
        ),
    },
    'perm_controller_g': {
        'build': 'GooglePermissionController',
        'update': (
            'adb install -r'
            ' $OUT/apex/com.google.android.permission/priv-app/GooglePermissionController/GooglePermissionController.apk'
        ),
    },
    'wifi': {
        'build': 'wifi',
        'update': (
            'adb install -r --staged --enable-rollback'
            ' $OUT/system/apex/com.android.wifi && adb shell am force-stop'
            ' com.android.wifi'
        ),
    },
    'vold': {'build': 'vold', 'update': 'adb shell am force-stop vold'},
    'multidisplay': {
        'build': 'multiDisplayProvider',
        'update': 'adb shell am force-stop com.android.emulator.multidisplay',
    },
    'wm_ext': {
        'build': 'androidx.window.extensions',
    },
    'rb': {
        'build': 'adServicesApk',
        'update': (
            'adb install'
            ' $OUT/apex/com.android.adservices/priv-app/AdServices/AdServices.apk'
        ),
    },
    'rb_g': {
        'build': 'adServicesApkGoogle',
        'update': (
            'adb install'
            ' $OUT/apex/com.google.android.adservices/priv-app/AdServicesApkGoogle@MASTER/AdServicesApkGoogle.apk'
        ),
    },
    'sdk_sandbox': {
        'build': 'sdkSandbox',
        'update': (
            'adb install'
            ' $OUT/apex/com.google.android.adservices/app/SdkSandboxGoogle@MASTER/SdkSandboxGoogle.apk'
        ),
    },
}


# Utilities to get type of target
def is_nexus():
  target_product = os.getenv('TARGET_PRODUCT')
  return (
      target_product.startswith('.aosp')
      or 'wembley' in target_product
      or 'gms_humuhumu' in target_product
  )


def create_alias_from_config(config):
  """Generates a Alias class from json."""
  alias = Alias()
  build = config.get('build', None)
  if build:
    alias.build = lambda: [f'm {build}']

  update = config.get('update', None)
  if update:
    alias.update = lambda: [
        'adevice update --restart=none',
        update,
    ]
  else:
    alias.update = lambda: ['adevice update']
  return alias


def get_aliases():
  """Dynamically find all aliases."""
  # definitions that subclass the Alias class
  aliases = {
      name.lower(): cls()
      for name, cls in inspect.getmembers(
          sys.modules[__name__], inspect.isclass
      )
      if issubclass(cls, Alias) and cls != Alias
  }
  # definitions that are defined in alias_definitions
  for name, config in alias_definitions.items():
    aliases[name.lower()] = create_alias_from_config(config)
  return aliases
