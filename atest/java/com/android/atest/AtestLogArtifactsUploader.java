/*
 * Copyright (C) 2024 The Android Open Source Project
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

import com.android.tradefed.config.Option;
import com.android.tradefed.invoker.TestInformation;
import com.android.tradefed.log.LogUtil.CLog;
import com.android.tradefed.targetprep.ITargetPreparer;

import java.io.File;
import com.android.tradefed.result.FileInputStreamSource;
import com.android.tradefed.log.ITestLogger;
import com.android.tradefed.result.ITestLoggerReceiver;
import com.android.tradefed.result.LogDataType;

/** A class to add Atest python artifacts to Tradefed logger. */
public final class AtestLogArtifactsUploader implements ITargetPreparer, ITestLoggerReceiver {

    @Option(name = "log-root-path", description = "root file system path to store log files.")
    private File mAtestRootReportDir;

    private ITestLogger mTestLogger;

    @Override
    public void setTestLogger(ITestLogger testLogger) {
        mTestLogger = testLogger;
    }

    @Override
    public void setUp(TestInformation testInfo) {
        // Intentionally left empty.
    }

    @Override
    public void tearDown(TestInformation testInfo, Throwable e) {
        if (mAtestRootReportDir == null) {
            CLog.d(
                    "Atest log root path not specified, skip adding python artifacts to test"
                            + " logger.");
            return;
        }

        String[] fileNames = new String[] {"atest.log", "test_result"};

        for (String fileName : fileNames) {
            File artifactFile = new File(mAtestRootReportDir.getParentFile(), fileName);
            if (!artifactFile.exists()) {
                continue;
            }
            mTestLogger.testLog(
                    fileName, LogDataType.HOST_LOG, new FileInputStreamSource(artifactFile));
        }
    }
}
