/*
 * Copyright (C) 2023 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.android.atest;

import com.android.tradefed.config.ConfigurationException;
import com.android.tradefed.config.Option;
import com.android.tradefed.config.OptionSetter;
import com.android.tradefed.device.DeviceNotAvailableException;
import com.android.tradefed.invoker.TestInformation;
import com.android.tradefed.result.ITestInvocationListener;
import com.android.tradefed.testtype.IRemoteTest;
import com.android.tradefed.testtype.ITestFilterReceiver;
import com.android.tradefed.testtype.python.PythonBinaryHostTest;

import java.io.File;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.Set;

public class AtestIntegrationPythonBinaryHostTest implements IRemoteTest, ITestFilterReceiver {
  private static final String OPTION_ARTIFACTS_PACK_PATH = "artifacts-pack-path";
  private PythonBinaryHostTest runner = new PythonBinaryHostTest();
  private Set<String> mIncludeFilters = new LinkedHashSet<>();
  private Set<String> mExcludeFilters = new LinkedHashSet<>();

  @Option(
      name = OPTION_ARTIFACTS_PACK_PATH,
      description = "Path of the artifacts pack.",
      mandatory = true)
  private File mArtifactsPackPath;

  @Option(
      name = "test-timeout",
      description = "Timeout for a single par file to terminate.",
      isTimeVal = true)
  private long mTestTimeout = -1;

  @Option(name = "par-file-name", description = "The binary names inside the build info to run.")
  private Set<String> mBinaryNames = new HashSet<>();

  private void setRunnerOptions() throws ConfigurationException {
    OptionSetter optionSetter = new OptionSetter(runner);

    optionSetter.setOptionValue("inject-serial-option", "true");
    optionSetter.setOptionValue("use-test-output-file", "true");
    optionSetter.setOptionValue("python-options", "-t");

    if (mArtifactsPackPath != null) {
      optionSetter.setOptionValue("python-options", "--artifacts_dir");
      optionSetter.setOptionValue("python-options", mArtifactsPackPath.getParent().toString());
    }
    if (mTestTimeout != -1) {
      optionSetter.setOptionValue("test-timeout", Long.toString(mTestTimeout));
    }
    for (String binaryName : mBinaryNames) {
      optionSetter.setOptionValue("par-file-name", binaryName);
    }
    runner.addAllIncludeFilters(mIncludeFilters);
    runner.addAllExcludeFilters(mExcludeFilters);
  }

  @Override
  public final void run(TestInformation testInfo, ITestInvocationListener listener)
      throws DeviceNotAvailableException {
    try {
      setRunnerOptions();
    } catch (ConfigurationException e) {
      throw new RuntimeException(e);
    }

    runner.run(testInfo, listener);
  }

  /** {@inheritDoc} */
  @Override
  public void addIncludeFilter(String filter) {
    mIncludeFilters.add(filter);
  }

  /** {@inheritDoc} */
  @Override
  public void addExcludeFilter(String filter) {
    mExcludeFilters.add(filter);
  }

  /** {@inheritDoc} */
  @Override
  public void addAllIncludeFilters(Set<String> filters) {
    mIncludeFilters.addAll(filters);
  }

  /** {@inheritDoc} */
  @Override
  public void addAllExcludeFilters(Set<String> filters) {
    mExcludeFilters.addAll(filters);
  }

  /** {@inheritDoc} */
  @Override
  public void clearIncludeFilters() {
    mIncludeFilters.clear();
  }

  /** {@inheritDoc} */
  @Override
  public void clearExcludeFilters() {
    mExcludeFilters.clear();
  }

  /** {@inheritDoc} */
  @Override
  public Set<String> getIncludeFilters() {
    return mIncludeFilters;
  }

  /** {@inheritDoc} */
  @Override
  public Set<String> getExcludeFilters() {
    return mExcludeFilters;
  }
}
