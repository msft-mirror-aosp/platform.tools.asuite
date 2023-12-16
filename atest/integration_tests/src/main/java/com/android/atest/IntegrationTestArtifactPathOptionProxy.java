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
import com.android.tradefed.config.IConfiguration;
import com.android.tradefed.config.IConfigurationReceiver;
import com.android.tradefed.config.Option;
import com.android.tradefed.config.OptionSetter;
import com.android.tradefed.invoker.TestInformation;
import com.android.tradefed.log.LogUtil.CLog;
import com.android.tradefed.result.error.InfraErrorIdentifier;
import com.android.tradefed.targetprep.ITargetPreparer;
import com.android.tradefed.targetprep.TargetSetupError;
import com.android.tradefed.testtype.IRemoteTest;
import com.android.tradefed.testtype.python.PythonBinaryHostTest;
import java.io.File;

// TODO: b/316223008 Remove this class after TradeFed native support to pass build artifact to
// python is implemented.
/** A temporary preparer for passing artifact path to the python script. */
public class IntegrationTestArtifactPathOptionProxy
        implements ITargetPreparer, IConfigurationReceiver {

    private static final String OPTION_ARTIFACTS_PACK_PATH = "artifacts-pack-path";

    @Option(
            name = OPTION_ARTIFACTS_PACK_PATH,
            description = "Path of the artifacts pack.",
            mandatory = false) // TODO: either set to true or use buildInfo.getFile() instead
    private File mArtifactsPackPath;

    private IConfiguration mConfig;

    /**
     * Gets the artifacts path from either the option value or build info.
     *
     * @param testInfo
     * @return artifacts path in string
     * @throws TargetSetupError
     */
    private String getArtifactsDirPath(TestInformation testInfo) throws TargetSetupError {
        // TODO: either use mArtifactsPackPath or buildInfo.getFile(). Decision will be made after
        // we get a working pipeline setup.
        String artifactsDir;
        String artifactPackFileName = "atest-integration-test-data.tar";
        if (mArtifactsPackPath != null) {
            CLog.d("mArtifactsPackPath = " + mArtifactsPackPath);
            artifactsDir =
                    mArtifactsPackPath.isFile() // TODO: assert on the file type
                            ? mArtifactsPackPath.getParent().toString()
                            : mArtifactsPackPath.toString();
        } else if (testInfo.getBuildInfo().getFile(artifactPackFileName) != null) {
            File artifactPath = testInfo.getBuildInfo().getFile(artifactPackFileName);
            CLog.d("BuildInfo().getFile = " + artifactPath);
            artifactsDir =
                    artifactPath.isFile()
                            ? artifactPath.getParent().toString()
                            : artifactPath.toString();
        } else {
            throw new TargetSetupError(
                    "Artifacts dir not found", InfraErrorIdentifier.OPTION_CONFIGURATION_ERROR);
        }
        return artifactsDir;
    }

    /** {@inheritDoc} */
    @Override
    public void setUp(TestInformation testInfo) throws TargetSetupError {
        CLog.d("Setting up artifact dir option");
        for (IRemoteTest t : mConfig.getTests()) {
            if (t instanceof PythonBinaryHostTest) {
                try {
                    OptionSetter optionSetter = new OptionSetter((PythonBinaryHostTest) t);
                    optionSetter.setOptionValue("python-options", "--artifacts_dir");
                    optionSetter.setOptionValue("python-options", getArtifactsDirPath(testInfo));
                } catch (ConfigurationException e) {
                    throw new TargetSetupError(
                            "Expected: Failed to set python option",
                            e,
                            InfraErrorIdentifier.OPTION_CONFIGURATION_ERROR);
                }
            }
        }
        CLog.d("Completed setting up artifacts dir option");
    }

    /** {@inheritDoc} */
    @Override
    public void setConfiguration(IConfiguration configuration) {
        mConfig = configuration;
    }

    /** Returns the configuration received through {@link #setConfiguration(IConfiguration)}. */
    public IConfiguration getConfiguration() {
        return mConfig;
    }
}
