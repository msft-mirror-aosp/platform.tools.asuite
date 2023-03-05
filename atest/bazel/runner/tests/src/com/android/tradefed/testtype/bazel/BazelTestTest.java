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
import static org.mockito.Mockito.anyLong;
import static org.mockito.Mockito.anyMap;
import static org.mockito.Mockito.argThat;
import static org.mockito.Mockito.contains;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

import com.android.tradefed.config.ConfigurationException;
import com.android.tradefed.config.OptionSetter;
import com.android.tradefed.invoker.InvocationContext;
import com.android.tradefed.invoker.TestInformation;
import com.android.tradefed.log.LogUtil.CLog;
import com.android.tradefed.result.error.ErrorIdentifier;
import com.android.tradefed.result.error.TestErrorIdentifier;
import com.android.tradefed.result.FailureDescription;
import com.android.tradefed.result.ILogSaverListener;
import com.android.tradefed.result.LogDataType;
import com.android.tradefed.result.LogFile;
import com.android.tradefed.result.proto.FileProtoResultReporter;
import com.android.tradefed.result.proto.TestRecordProto.FailureStatus;
import com.android.tradefed.result.TestDescription;
import com.android.tradefed.util.ZipUtil;

import com.google.common.base.Splitter;
import com.google.common.collect.ImmutableMap;
import com.google.common.io.MoreFiles;
import com.google.common.util.concurrent.Uninterruptibles;
import com.google.devtools.build.lib.buildeventstream.BuildEventStreamProtos;

import org.junit.Before;
import org.junit.Rule;
import org.junit.rules.TemporaryFolder;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.junit.Test;
import org.mockito.ArgumentMatcher;
import org.mockito.InOrder;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.TimeUnit;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.Random;
import java.util.stream.Collectors;
import java.util.stream.Stream;

@RunWith(JUnit4.class)
public final class BazelTestTest {

    private ILogSaverListener mMockListener;
    private TestInformation mTestInfo;
    private Path mBazelTempPath;
    private Map<String, String> mEnvironment;
    private Path mWorkspaceArchive;

    private static final String BAZEL_TEST_TARGETS_OPTION = "bazel-test-target-patterns";
    private static final String BAZEL_WORKSPACE_ARCHIVE_OPTION = "bazel-workspace-archive";
    private static final String BEP_FILE_OPTION_NAME = "--build_event_binary_file";
    private static final long RANDOM_SEED = 1234567890L;

    @Rule public final TemporaryFolder tempDir = new TemporaryFolder();

    @Before
    public void setUp() throws Exception {
        mMockListener = mock(ILogSaverListener.class);
        InvocationContext context = new InvocationContext();
        context.addInvocationAttribute("module-id", "bazel-test-module-id");
        mTestInfo = TestInformation.newBuilder().setInvocationContext(context).build();
        mBazelTempPath =
                Files.createDirectory(tempDir.getRoot().toPath().resolve("bazel_temp_dir"));
        mEnvironment = ImmutableMap.of("PATH", "/phony/path");
        Path bazelArchive =
                Files.createDirectory(tempDir.getRoot().toPath().resolve("atest_bazel_workspace"));
        mWorkspaceArchive = tempDir.getRoot().toPath().resolve("atest_bazel_workspace.zip");
        ZipUtil.createZip(bazelArchive.toFile(), mWorkspaceArchive.toFile());
    }

    @Test
    public void runSucceeds_invokesListenerEvents() throws Exception {
        BazelTest bazelTest = newBazelTest();

        bazelTest.run(mTestInfo, mMockListener);

        verify(mMockListener).testRunStarted(eq(BazelTest.class.getName()), eq(0));
        verify(mMockListener).testRunEnded(anyLong(), anyMap());
    }

    @Test
    public void runSucceeds_tempDirEmptied() throws Exception {
        BazelTest bazelTest = newBazelTest();

        bazelTest.run(mTestInfo, mMockListener);

        assertThat(listDirContents(mBazelTempPath)).isEmpty();
    }

    @Test
    public void runSucceeds_logsSaved() throws Exception {
        BazelTest bazelTest = newBazelTest();

        bazelTest.run(mTestInfo, mMockListener);

        verify(mMockListener)
                .testLog(contains(String.format("%s-log", BazelTest.QUERY_TARGETS)), any(), any());
        verify(mMockListener)
                .testLog(contains(String.format("%s-log", BazelTest.RUN_TESTS)), any(), any());
    }

    @Test
    public void runSucceeds_testLogsReportedUnderModule() throws Exception {
        BazelTest bazelTest = newBazelTest();

        bazelTest.run(mTestInfo, mMockListener);

        InOrder inOrder = inOrder(mMockListener);
        inOrder.verify(mMockListener).testModuleStarted(any());
        inOrder.verify(mMockListener)
                .testLog(eq("tf-test-process-module-log"), eq(LogDataType.TAR_GZ), any());
        inOrder.verify(mMockListener)
                .testLog(eq("tf-test-process-invocation-log"), eq(LogDataType.XML), any());
        inOrder.verify(mMockListener).testModuleEnded();
    }

    @Test
    public void malformedProtoResults_runFails() throws Exception {
        FakeProcessStarter processStarter = newFakeProcessStarter();
        processStarter.put(
                BazelTest.RUN_TESTS,
                builder -> {
                    return new FakeBazelTestProcess(builder, mBazelTempPath) {
                        @Override
                        public void writeSingleTestOutputs(Path outputsDir, String testName)
                                throws IOException, ConfigurationException {

                            super.writeSingleTestOutputs(outputsDir, testName);

                            Path outputFile = outputsDir.resolve("proto-results");
                            Files.write(outputFile, "Malformed Proto File".getBytes());
                        }
                    };
                });
        BazelTest bazelTest = newBazelTestWithProcessStarter(processStarter);

        bazelTest.run(mTestInfo, mMockListener);

        verify(mMockListener).testRunFailed(hasFailureStatus(FailureStatus.INFRA_FAILURE));
    }

    @Test
    public void malformedBepFile_runFails() throws Exception {
        FakeProcessStarter processStarter = newFakeProcessStarter();
        processStarter.put(
                BazelTest.RUN_TESTS,
                builder -> {
                    return new FakeBazelTestProcess(builder, mBazelTempPath) {
                        @Override
                        public void writeSingleTestResultEvent(File outputsZipFile, Path bepFile)
                                throws IOException {

                            Files.write(bepFile, "Malformed BEP File".getBytes());
                        }
                    };
                });
        BazelTest bazelTest = newBazelTestWithProcessStarter(processStarter);

        bazelTest.run(mTestInfo, mMockListener);

        verify(mMockListener).testRunFailed(hasFailureStatus(FailureStatus.TEST_FAILURE));
    }

    @Test
    public void bepFileMissingLastMessage_runFails() throws Exception {
        FakeProcessStarter processStarter = newFakeProcessStarter();
        processStarter.put(
                BazelTest.RUN_TESTS,
                builder -> {
                    return new FakeBazelTestProcess(builder, mBazelTempPath) {
                        @Override
                        public void writeLastEvent() throws IOException {
                            // Do nothing.
                        }
                    };
                });
        BazelTest bazelTest = newBazelTestWithProcessStarter(processStarter);

        bazelTest.run(mTestInfo, mMockListener);

        verify(mMockListener).testRunFailed(hasFailureStatus(FailureStatus.INFRA_FAILURE));
    }

    @Test
    public void targetsNotSet_testsAllTargets() throws Exception {
        String targetName = "customTestTarget";
        List<String> command = new ArrayList<>();
        FakeProcessStarter processStarter = newFakeProcessStarter();
        processStarter.put(BazelTest.QUERY_TARGETS, newPassingProcessWithStdout(targetName));
        processStarter.put(
                BazelTest.RUN_TESTS,
                builder -> {
                    command.addAll(builder.command());
                    return new FakeBazelTestProcess(builder, mBazelTempPath);
                });
        BazelTest bazelTest = newBazelTestWithProcessStarter(processStarter);

        bazelTest.run(mTestInfo, mMockListener);

        assertThat(command).contains(targetName);
    }

    @Test
    public void archiveExtractionFails_runAborted() throws Exception {
        BazelTest bazelTest = new BazelTest(newFakeProcessStarter(), mBazelTempPath);
        OptionSetter setter = new OptionSetter(bazelTest);
        setter.setOptionValue(
                BAZEL_WORKSPACE_ARCHIVE_OPTION,
                new File("non_existent_workspace.zip").getAbsolutePath());

        bazelTest.run(mTestInfo, mMockListener);

        verify(mMockListener).testRunFailed(hasErrorIdentifier(TestErrorIdentifier.TEST_ABORTED));
    }

    @Test
    public void bazelQueryFails_runAborted() throws Exception {
        FakeProcessStarter processStarter = newFakeProcessStarter();
        processStarter.put(BazelTest.QUERY_TARGETS, newFailingProcess());
        BazelTest bazelTest = newBazelTestWithProcessStarter(processStarter);

        bazelTest.run(mTestInfo, mMockListener);

        verify(mMockListener).testRunFailed(hasErrorIdentifier(TestErrorIdentifier.TEST_ABORTED));
    }

    @Test
    public void testTimeout_causesTestFailure() throws Exception {
        FakeProcessStarter processStarter = newFakeProcessStarter();
        processStarter.put(
                BazelTest.RUN_TESTS,
                builder -> {
                    return new FakeBazelTestProcess(builder, mBazelTempPath) {
                        @Override
                        public boolean waitFor(long timeout, TimeUnit unit) {
                            return false;
                        }
                    };
                });
        BazelTest bazelTest = newBazelTestWithProcessStarter(processStarter);

        bazelTest.run(mTestInfo, mMockListener);

        verify(mMockListener).testRunFailed(hasFailureStatus(FailureStatus.TIMED_OUT));
    }

    @Test
    public void customTargetOption_testsCustomTargets() throws Exception {
        String targetName = "//my/custom:test";
        List<String> command = new ArrayList<>();
        FakeProcessStarter processStarter = newFakeProcessStarter();
        processStarter.put(
                BazelTest.RUN_TESTS,
                builder -> {
                    command.addAll(builder.command());
                    return new FakeBazelTestProcess(builder, mBazelTempPath);
                });
        BazelTest bazelTest = newBazelTestWithProcessStarter(processStarter);
        OptionSetter setter = new OptionSetter(bazelTest);
        setter.setOptionValue(BAZEL_TEST_TARGETS_OPTION, targetName);

        bazelTest.run(mTestInfo, mMockListener);

        assertThat(command).contains(targetName);
    }

    @Test
    public void queryStdoutEmpty_abortsRun() throws Exception {
        FakeProcessStarter processStarter = newFakeProcessStarter();
        processStarter.put(BazelTest.QUERY_TARGETS, newPassingProcessWithStdout(""));
        BazelTest bazelTest = newBazelTestWithProcessStarter(processStarter);

        bazelTest.run(mTestInfo, mMockListener);

        verify(mMockListener).testRunFailed(hasErrorIdentifier(TestErrorIdentifier.TEST_ABORTED));
    }

    @Test
    public void multipleTestsRun_reportsAllResults() throws Exception {
        int testCount = 3;
        Duration testDelay = Duration.ofMillis(10);
        final AtomicLong testTime = new AtomicLong();
        FakeProcessStarter processStarter = newFakeProcessStarter();
        byte[] bytes = logFileContents();

        processStarter.put(
                BazelTest.RUN_TESTS,
                builder -> {
                    return new FakeBazelTestProcess(builder, mBazelTempPath) {
                        @Override
                        public Path createLogFile(String testName, Path logDir) throws IOException {
                            Path logFile = logDir.resolve(testName);
                            Files.write(logFile, bytes);
                            return logFile;
                        }

                        @Override
                        public void runTests() throws IOException, ConfigurationException {
                            long start = System.nanoTime();
                            for (int i = 0; i < testCount; i++) {
                                runSingleTest("test-" + i);
                            }
                            testTime.set((System.nanoTime() - start) / 1000000);
                        }

                        @Override
                        void singleTestBody() {
                            Uninterruptibles.sleepUninterruptibly(
                                    testDelay.toMillis(), TimeUnit.MILLISECONDS);
                        }
                    };
                });
        BazelTest bazelTest = newBazelTestWithProcessStarter(processStarter);

        long start = System.nanoTime();
        bazelTest.run(mTestInfo, mMockListener);
        long totalTime = ((System.nanoTime() - start) / 1000000);

        // TODO(b/267378279): Consider converting this test to a proper benchmark instead of using
        // logging.
        CLog.i("Total runtime: " + totalTime + "ms, test time: " + testTime.get() + "ms.");

        verify(mMockListener, times(testCount)).testStarted(any(), anyLong());
    }

    private static byte[] logFileContents() {
        // Seed Random to always get the same sequence of values.
        Random rand = new Random(RANDOM_SEED);
        byte[] bytes = new byte[1024 * 1024];
        rand.nextBytes(bytes);
        return bytes;
    }

    private static FakeProcess newPassingProcess() {
        return new FakeProcess() {
            @Override
            public int exitValue() {
                return 0;
            }
        };
    }

    private static FakeProcess newFailingProcess() {
        return new FakeProcess() {
            @Override
            public int exitValue() {
                return -1;
            }
        };
    }

    private static FakeProcess newPassingProcessWithStdout(String stdOut) {
        return new FakeProcess() {
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

    private BazelTest newBazelTestWithProcessStarter(BazelTest.ProcessStarter starter)
            throws Exception {

        BazelTest bazelTest = new BazelTest(starter, mBazelTempPath);
        OptionSetter setter = new OptionSetter(bazelTest);
        setter.setOptionValue(
                BAZEL_WORKSPACE_ARCHIVE_OPTION, mWorkspaceArchive.toAbsolutePath().toString());
        return bazelTest;
    }

    private BazelTest newBazelTest() throws Exception {
        return newBazelTestWithProcessStarter(newFakeProcessStarter());
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

    private FakeProcessStarter newFakeProcessStarter() throws IOException {
        FakeProcessStarter processStarter = new FakeProcessStarter();
        processStarter.put(BazelTest.QUERY_TARGETS, newPassingProcessWithStdout("default_target"));
        processStarter.put(
                BazelTest.RUN_TESTS,
                builder -> {
                    return new FakeBazelTestProcess(builder, mBazelTempPath);
                });
        return processStarter;
    }

    private static List<Path> listDirContents(Path dir) throws IOException {
        try (Stream<Path> fileStream = Files.list(dir)) {
            return fileStream.collect(Collectors.toList());
        }
    }

    private static final class FakeProcessStarter implements BazelTest.ProcessStarter {
        private final Map<String, Function<ProcessBuilder, FakeProcess>> mTagToProcess =
                new HashMap<>();

        @Override
        public Process start(String tag, ProcessBuilder builder) throws IOException {
            FakeProcess process = mTagToProcess.get(tag).apply(builder);
            process.start();
            return process;
        }

        public void put(String tag, FakeProcess process) {
            mTagToProcess.put(
                    tag,
                    b -> {
                        return process;
                    });
        }

        public void put(String tag, Function<ProcessBuilder, FakeProcess> process) {
            mTagToProcess.put(tag, process);
        }
    }

    private abstract static class FakeProcess extends Process {

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

        public void start() throws IOException {
            return;
        }
    }

    private static class FakeBazelTestProcess extends FakeProcess {
        private final Path mBepFile;
        private final Path mBazelTempDirectory;

        public FakeBazelTestProcess(ProcessBuilder builder, Path bazelTempDir) {
            mBepFile =
                    Paths.get(
                            builder.command().stream()
                                    .map(s -> Splitter.on('=').splitToList(s))
                                    .filter(s -> s.get(0).equals(BEP_FILE_OPTION_NAME))
                                    .findFirst()
                                    .get()
                                    .get(1));
            mBazelTempDirectory = bazelTempDir;
        }

        @Override
        public void start() throws IOException {
            try {
                runTests();
                writeLastEvent();
            } catch (ConfigurationException e) {
                throw new RuntimeException(e);
            }
        }

        void runTests() throws IOException, ConfigurationException {
            runSingleTest("test-1");
        }

        void runSingleTest(String testName) throws IOException, ConfigurationException {
            Path outputDir = Files.createTempDirectory(mBazelTempDirectory, testName);
            try {
                singleTestBody();
                writeSingleTestOutputs(outputDir, testName);
                File outputsZipFile = zipSingleTestOutputsDirectory(outputDir);
                writeSingleTestResultEvent(outputsZipFile, mBepFile);
            } finally {
                MoreFiles.deleteRecursively(outputDir);
            }
        }

        void singleTestBody() {
            // Do nothing.
        }

        void writeSingleTestOutputs(Path outputsDir, String testName)
                throws IOException, ConfigurationException {

            FileProtoResultReporter reporter = new FileProtoResultReporter();
            OptionSetter setter = new OptionSetter(reporter);
            Path outputFile = outputsDir.resolve("proto-results");
            setter.setOptionValue("proto-output-file", outputFile.toAbsolutePath().toString());

            Path logDir = Files.createDirectories(outputsDir.resolve("stub/-1/stub"));
            Path isolatedJavaLog = createLogFile("isolated-java-logs.tar.gz", logDir);
            Path tfConfig = createLogFile("tradefed-expanded-config.xml", logDir);

            InvocationContext context = new InvocationContext();
            context.addInvocationAttribute("module-id", "single-tradefed-test-module-id");

            reporter.invocationStarted(context);
            reporter.testModuleStarted(context);
            reporter.testRunStarted("test-run", 1);
            TestDescription testD = new TestDescription("class-name", testName);
            reporter.testStarted(testD);
            reporter.testEnded(testD, Collections.emptyMap());
            reporter.testRunEnded(0, Collections.emptyMap());
            reporter.logAssociation(
                    "module-log",
                    new LogFile(
                            isolatedJavaLog.toAbsolutePath().toString(), "", LogDataType.TAR_GZ));
            reporter.testModuleEnded();
            reporter.logAssociation(
                    "invocation-log",
                    new LogFile(tfConfig.toAbsolutePath().toString(), "", LogDataType.XML));
            reporter.invocationEnded(0);
        }

        Path createLogFile(String testName, Path logDir) throws IOException {
            Path logFile = logDir.resolve(testName);
            Files.write(logFile, testName.getBytes());
            return logFile;
        }

        File zipSingleTestOutputsDirectory(Path outputsDir) throws IOException {
            List<File> files =
                    listDirContents(outputsDir).stream()
                            .map(f -> f.toFile())
                            .collect(Collectors.toList());
            return ZipUtil.createZip(files);
        }

        void writeSingleTestResultEvent(File outputsZipFile, Path bepFile) throws IOException {
            try (FileOutputStream bepOutputStream = new FileOutputStream(bepFile.toFile(), true)) {
                BuildEventStreamProtos.BuildEvent.newBuilder()
                        .setId(
                                BuildEventStreamProtos.BuildEventId.newBuilder()
                                        .setTestResult(
                                                BuildEventStreamProtos.BuildEventId.TestResultId
                                                        .getDefaultInstance())
                                        .build())
                        .setTestResult(
                                BuildEventStreamProtos.TestResult.newBuilder()
                                        .addTestActionOutput(
                                                BuildEventStreamProtos.File.newBuilder()
                                                        .setName("test.outputs__outputs.zip")
                                                        .setUri(outputsZipFile.getAbsolutePath())
                                                        .build())
                                        .build())
                        .build()
                        .writeDelimitedTo(bepOutputStream);
            }
        }

        void writeLastEvent() throws IOException {
            try (FileOutputStream bepOutputStream = new FileOutputStream(mBepFile.toFile(), true)) {
                BuildEventStreamProtos.BuildEvent.newBuilder()
                        .setId(BuildEventStreamProtos.BuildEventId.getDefaultInstance())
                        .setProgress(BuildEventStreamProtos.Progress.getDefaultInstance())
                        .setLastMessage(true)
                        .build()
                        .writeDelimitedTo(bepOutputStream);
            }
        }
    }
}
