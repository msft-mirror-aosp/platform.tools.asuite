/*
 * Copyright (C) 2022 The Android Open Source Project
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
package com.android.tradefed.testtype.bazel;

import static com.google.common.truth.Truth.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.argThat;
import static org.mockito.Mockito.anyLong;
import static org.mockito.Mockito.anyMap;
import static org.mockito.Mockito.contains;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.spy;

import com.android.tradefed.build.BuildInfo;
import com.android.tradefed.build.IBuildInfo;
import com.android.tradefed.config.OptionSetter;
import com.android.tradefed.device.ITestDevice;
import com.android.tradefed.invoker.InvocationContext;
import com.android.tradefed.invoker.TestInformation;
import com.android.tradefed.result.FailureDescription;
import com.android.tradefed.result.ITestInvocationListener;
import com.android.tradefed.result.error.ErrorIdentifier;
import com.android.tradefed.result.error.InfraErrorIdentifier;
import com.android.tradefed.result.error.TestErrorIdentifier;
import com.android.tradefed.result.proto.TestRecordProto.FailureStatus;
import com.google.common.collect.ImmutableMap;

import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.ArgumentMatcher;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.TimeUnit;
import java.util.HashMap;
import java.util.Map;
import java.util.stream.Collectors;

@RunWith(JUnit4.class)
public final class BazelTestTest {

    private ITestInvocationListener mMockListener;
    private ITestDevice mMockDevice;
    private TestInformation mTestInfo;
    private IBuildInfo mBuildInfo;
    private Path mTempPath;
    private Map<String, String> mEnvironment;

    private static final String ARCHIVE_PATH = "/path/to/atest_bazel_workspace.tar.gz";
    private static final String ARCHIVE_NAME = "atest_bazel_workspace.tar.gz";
    private static final String BAZEL_TEST_TARGETS_OPTION = "bazel-test-target-patterns";
    private static final String BAZEL_WORKSPACE_ARCHIVE_OPTION = "bazel-workspace-archive";

    @Rule public final TemporaryFolder tempDir = new TemporaryFolder();

    @Before
    public void setUp() {
        mMockListener = mock(ITestInvocationListener.class);
        mMockDevice = mock(ITestDevice.class);
        mBuildInfo = new BuildInfo();
        mBuildInfo.setFile("atest_bazel_workspace.tar.gz", new File(ARCHIVE_PATH), "1.0");
        InvocationContext context = new InvocationContext();
        context.addAllocatedDevice("device", mMockDevice);
        context.addDeviceBuildInfo("device", mBuildInfo);
        mTestInfo = TestInformation.newBuilder().setInvocationContext(context).build();
        mTempPath = tempDir.getRoot().toPath();
        mEnvironment = ImmutableMap.of("PATH", "/phony/path");
    }

    @Test
    public void runSucceeds_invokesListenerEvents() throws Exception {
        BazelTest bazelTest = newBazelTest();

        bazelTest.run(mTestInfo, mMockListener);

        verify(mMockListener).testRunStarted(eq(BazelTest.class.getName()), eq(1));
        verify(mMockListener).testRunEnded(anyLong(), anyMap());
    }

    @Test
    public void runSucceeds_tempDirEmptied() throws Exception {
        BazelTest bazelTest = newBazelTest();

        bazelTest.run(mTestInfo, mMockListener);

        assertThat(Files.list(mTempPath).collect(Collectors.toList())).isEmpty();
    }

    @Test
    public void runSucceeds_logsSaved() throws Exception {
        BazelTest bazelTest = newBazelTest();

        bazelTest.run(mTestInfo, mMockListener);

        verify(mMockListener)
                .testLog(
                        contains(String.format("%s-log", BazelTest.EXTRACT_ARCHIVE)), any(), any());
        verify(mMockListener)
                .testLog(contains(String.format("%s-log", BazelTest.QUERY_TARGETS)), any(), any());
        verify(mMockListener)
                .testLog(contains(String.format("%s-log", BazelTest.RUN_TESTS)), any(), any());
    }

    @Test
    public void targetsNotSet_testsAllTargets() throws Exception {
        String targetName = "customTestTarget";
        TestProcessStarter processStarter = spy(newTestProcessStarter());
        processStarter.put(BazelTest.QUERY_TARGETS, newPassingProcessWithStdout(targetName));
        BazelTest bazelTest = newBazelTest(processStarter);

        bazelTest.run(mTestInfo, mMockListener);

        verify(processStarter).start(eq(BazelTest.RUN_TESTS), hasCommandElement(targetName));
    }

    @Test
    public void archiveNotFound_runAborted() throws Exception {
        BazelTest bazelTest = newBazelTest();

        bazelTest.run(newTestInformationWithoutArchive(), mMockListener);

        verify(mMockListener)
                .testRunFailed(hasErrorIdentifier(InfraErrorIdentifier.ARTIFACT_NOT_FOUND));
    }

    @Test
    public void archiveExtractionFails_runAborted() throws Exception {
        TestProcessStarter processStarter = newTestProcessStarter();
        processStarter.put(BazelTest.EXTRACT_ARCHIVE, newFailingProcess());
        BazelTest bazelTest = newBazelTest(processStarter);

        bazelTest.run(mTestInfo, mMockListener);

        verify(mMockListener).testRunFailed(hasErrorIdentifier(TestErrorIdentifier.TEST_ABORTED));
    }

    @Test
    public void bazelQueryFails_runAborted() throws Exception {
        TestProcessStarter processStarter = newTestProcessStarter();
        processStarter.put(BazelTest.QUERY_TARGETS, newFailingProcess());
        BazelTest bazelTest = newBazelTest(processStarter);

        bazelTest.run(mTestInfo, mMockListener);

        verify(mMockListener).testRunFailed(hasErrorIdentifier(TestErrorIdentifier.TEST_ABORTED));
    }

    @Test
    public void testTimeout_causesTestFailure() throws Exception {
        TestProcessStarter processStarter = newTestProcessStarter();
        processStarter.put(BazelTest.RUN_TESTS, newEternalProcess());
        BazelTest bazelTest = newBazelTest(processStarter);

        bazelTest.run(mTestInfo, mMockListener);

        verify(mMockListener).testFailed(any(), hasFailureStatus(FailureStatus.TIMED_OUT));
    }

    @Test
    public void customTargetOption_testsCustomTargets() throws Exception {
        TestProcessStarter processStarter = spy(newTestProcessStarter());
        BazelTest bazelTest = newBazelTest(processStarter);
        String targetName = "//my/custom:test";
        OptionSetter setter = new OptionSetter(bazelTest);
        setter.setOptionValue(BAZEL_TEST_TARGETS_OPTION, targetName);

        bazelTest.run(mTestInfo, mMockListener);

        verify(processStarter).start(eq(BazelTest.RUN_TESTS), hasCommandElement(targetName));
    }

    @Test
    public void queryStdoutEmpty_abortsRun() throws Exception {
        TestProcessStarter processStarter = newTestProcessStarter();
        processStarter.put(BazelTest.QUERY_TARGETS, newPassingProcessWithStdout(""));
        BazelTest bazelTest = newBazelTest(processStarter);

        bazelTest.run(mTestInfo, mMockListener);

        verify(mMockListener).testRunFailed(hasErrorIdentifier(TestErrorIdentifier.TEST_ABORTED));
    }

    private static Process newPassingProcess() {
        return new TestProcess() {
            @Override
            public int exitValue() {
                return 0;
            }
        };
    }

    private static Process newFailingProcess() {
        return new TestProcess() {
            @Override
            public int exitValue() {
                return -1;
            }
        };
    }

    private static Process newEternalProcess() {
        return new TestProcess() {
            @Override
            public boolean waitFor(long timeout, TimeUnit unit) {
                return false;
            }
        };
    }

    private static Process newPassingProcessWithStdout(String stdOut) {
        return new TestProcess() {
            @Override
            public int exitValue() {
                return 0;
            }

            @Override
            public InputStream getInputStream() {
                return new ByteArrayInputStream(stdOut.getBytes());
            }
        };
    }

    private static TestInformation newTestInformationWithoutArchive() {
        return TestInformation.newBuilder().setInvocationContext(new InvocationContext()).build();
    }

    private static void setBazelArchiveOption(BazelTest bazelTest) throws Exception {
        OptionSetter setter = new OptionSetter(bazelTest);
        setter.setOptionValue(BAZEL_WORKSPACE_ARCHIVE_OPTION, ARCHIVE_NAME);
    }

    private BazelTest newBazelTest(BazelTest.ProcessStarter starter) throws Exception {
        BazelTest bazelTest = new BazelTest(starter, mEnvironment, mTempPath);
        setBazelArchiveOption(bazelTest);
        return bazelTest;
    }

    private BazelTest newBazelTest() throws Exception {
        BazelTest bazelTest = new BazelTest(newTestProcessStarter(), mEnvironment, mTempPath);
        setBazelArchiveOption(bazelTest);
        return bazelTest;
    }

    private static FailureDescription hasErrorIdentifier(ErrorIdentifier error) {
        return argThat(
                new ArgumentMatcher<FailureDescription>() {
                    @Override
                    public boolean matches(FailureDescription right) {
                        return right.getErrorIdentifier().equals(error);
                    }
                });
    }

    private static FailureDescription hasFailureStatus(FailureStatus status) {
        return argThat(
                new ArgumentMatcher<FailureDescription>() {
                    @Override
                    public boolean matches(FailureDescription right) {
                        return right.getFailureStatus().equals(status);
                    }
                });
    }

    private static ProcessBuilder hasCommandElement(String element) {
        return argThat(
                new ArgumentMatcher<ProcessBuilder>() {
                    @Override
                    public boolean matches(ProcessBuilder right) {
                        return right.command().contains(element);
                    }
                });
    }

    private static TestProcessStarter newTestProcessStarter() {
        TestProcessStarter processStarter = new TestProcessStarter();
        processStarter.put(BazelTest.QUERY_TARGETS, newPassingProcessWithStdout("default_target"));
        return processStarter;
    }

    private static class TestProcessStarter implements BazelTest.ProcessStarter {
        private final Map<String, Process> mTagToProcess = new HashMap<>();
        private final Process mDefaultProcess = newPassingProcess();

        @Override
        public Process start(String tag, ProcessBuilder builder) {
            Process process = mTagToProcess.get(tag);

            if (process == null) {
                return mDefaultProcess;
            }
            return process;
        }

        public void put(String tag, Process process) {
            mTagToProcess.put(tag, process);
        }
    }

    private abstract static class TestProcess extends Process {

        @Override
        public void destroy() {
            return;
        }

        @Override
        public int exitValue() {
            return 0;
        }

        @Override
        public InputStream getErrorStream() {
            return new ByteArrayInputStream("".getBytes());
        }

        @Override
        public InputStream getInputStream() {
            return new ByteArrayInputStream("".getBytes());
        }

        @Override
        public OutputStream getOutputStream() {
            return new ByteArrayOutputStream(0);
        }

        @Override
        public int waitFor() {
            return 0;
        }
    }
}
