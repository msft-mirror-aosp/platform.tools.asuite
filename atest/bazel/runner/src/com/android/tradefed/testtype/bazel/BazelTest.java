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

import com.android.annotations.VisibleForTesting;
import com.android.tradefed.config.Option;
import com.android.tradefed.config.OptionClass;
import com.android.tradefed.device.DeviceNotAvailableException;
import com.android.tradefed.invoker.IInvocationContext;
import com.android.tradefed.invoker.TestInformation;
import com.android.tradefed.log.ITestLogger;
import com.android.tradefed.log.LogUtil.CLog;
import com.android.tradefed.result.FailureDescription;
import com.android.tradefed.result.FileInputStreamSource;
import com.android.tradefed.result.ITestInvocationListener;
import com.android.tradefed.result.LogDataType;
import com.android.tradefed.result.error.ErrorIdentifier;
import com.android.tradefed.result.error.TestErrorIdentifier;
import com.android.tradefed.result.proto.TestRecordProto.FailureStatus;
import com.android.tradefed.testtype.IRemoteTest;
import com.android.tradefed.util.StreamUtil;
import com.google.common.base.Joiner;
import com.google.common.collect.ImmutableMap;
import com.google.common.io.CharStreams;
import com.google.common.io.MoreFiles;

import java.io.File;
import java.io.InputStreamReader;
import java.io.IOException;
import java.lang.ProcessBuilder.Redirect;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Collections;
import java.util.concurrent.TimeUnit;
import java.util.List;
import java.util.Map;
import java.time.Duration;

/** Test runner for executing Bazel tests. */
@OptionClass(alias = "bazel-test")
public final class BazelTest implements IRemoteTest {

    public static final String EXTRACT_ARCHIVE = "extract_archive";
    public static final String QUERY_TARGETS = "query_targets";
    public static final String RUN_TESTS = "run_tests";

    private static final Duration ARCHIVE_EXTRACTION_TIMEOUT = Duration.ofHours(1L);
    private static final Duration BAZEL_QUERY_TIMEOUT = Duration.ofMinutes(5);
    private static final String TEST_NAME = BazelTest.class.getName();

    private final List<Path> mTemporaryPaths = new ArrayList<>();
    private final List<Path> mLogFiles = new ArrayList<>();
    private final ImmutableMap<String, String> mEnvironment;
    private final ProcessStarter mProcessStarter;
    private final Path mTemporaryDirectory;

    private Path mRunTemporaryDirectory;

    @Option(
            name = "bazel-test-command-timeout",
            description = "Timeout for running the Bazel test.")
    private Duration mBazelCommandTimeout = Duration.ofHours(1L);

    @Option(
            name = "bazel-workspace-archive",
            description = "Location of the Bazel workspace archive.")
    private File mBazelWorkspaceArchive;

    @Option(
            name = "bazel-startup-options",
            description = "List of startup options to be passed to Bazel.")
    private final List<String> mBazelStartupOptions = new ArrayList<>();

    @Option(
            name = "bazel-test-target-patterns",
            description =
                    "Target labels for test targets to run, default is to query workspace archive"
                            + " for all tests and run those.")
    private final List<String> mTestTargetPatterns = new ArrayList<>();

    @Option(
            name = "bazel-test-extra-args",
            description = "List of extra arguments to be passed to Bazel")
    private final List<String> mBazelTestExtraArgs = new ArrayList<>();

    @Option(
            name = "extra-tradefed-jars",
            description = "List of jars to add to Tradefed's classpath.")
    private final List<File> mExtraTradefedJars = new ArrayList<>();

    @Option(
            name = "bazel-max-idle-timout",
            description = "Max idle timeout in seconds for bazel commands.")
    private Duration mBazelMaxIdleTimeout = Duration.ofSeconds(5L);

    public BazelTest() {
        mProcessStarter = new DefaultProcessStarter();
        mEnvironment = ImmutableMap.copyOf(System.getenv());
        mTemporaryDirectory = Paths.get(System.getProperty("java.io.tmpdir"));
    }

    @VisibleForTesting
    BazelTest(ProcessStarter processStarter, Map<String, String> environment, Path tmpDir) {
        mProcessStarter = processStarter;
        mEnvironment = ImmutableMap.copyOf(environment);
        mTemporaryDirectory = tmpDir;
    }

    @Override
    public void run(TestInformation testInfo, ITestInvocationListener listener)
            throws DeviceNotAvailableException {

        long startTime = System.currentTimeMillis();

        FailureDescription infraRunFailure = null;

        try {
            initialize();
            Path workspaceDirectory = extractWorkspace(mBazelWorkspaceArchive.toPath());

            List<String> testTargets = listTestTargets(workspaceDirectory);
            if (testTargets.isEmpty()) {
                throw new AbortRunException(
                        "No targets found, aborting.",
                        FailureStatus.DEPENDENCY_ISSUE,
                        TestErrorIdentifier.TEST_ABORTED);
            }

            runTests(testInfo, listener, testTargets, workspaceDirectory);
        } catch (IOException | InterruptedException e) {
            CLog.e(e);
            infraRunFailure =
                    throwableToFailureDescription(e).setFailureStatus(FailureStatus.TEST_FAILURE);
        } catch (AbortRunException e) {
            CLog.e(e);
            infraRunFailure = e.getFailureDescription();
        }

        listener.testModuleStarted(testInfo.getContext());
        listener.testRunStarted(TEST_NAME, 0);
        if (infraRunFailure != null) {
            listener.testRunFailed(infraRunFailure);
        }
        listener.testRunEnded(System.currentTimeMillis() - startTime, Collections.emptyMap());
        listener.testModuleEnded();

        addTestLogs(listener);
        cleanup();
    }

    private void initialize() throws IOException {
        mRunTemporaryDirectory = Files.createTempDirectory(mTemporaryDirectory, "bazel-test-");
    }

    private Path extractWorkspace(Path workspaceArchive) throws IOException, InterruptedException {
        Path outputDirectory = createTemporaryDirectory("atest-bazel-workspace-");
        Path logFile = createLogFile(String.format("%s-log", EXTRACT_ARCHIVE));

        ProcessBuilder builder =
                new ProcessBuilder(
                        "tar",
                        "zxf",
                        workspaceArchive.toAbsolutePath().toString(),
                        "-C",
                        outputDirectory.toAbsolutePath().toString());

        builder.redirectErrorStream(true);
        builder.redirectOutput(Redirect.appendTo(logFile.toFile()));

        startAndWaitForProcess(EXTRACT_ARCHIVE, builder, ARCHIVE_EXTRACTION_TIMEOUT);

        // TODO(b/233885171): Remove resolve once workspace archive is updated.
        Path workspaceDirectory = outputDirectory.resolve("out/atest_bazel_workspace");

        // TODO(b/230764993): Switch to using this flag once implemented.
        if (!mExtraTradefedJars.isEmpty()) {
            copyExtraTradefedJars(workspaceDirectory);
        }

        return workspaceDirectory;
    }

    private ProcessBuilder createBazelCommand(Path workspaceDirectory, String tmpDirPrefix)
            throws IOException {
        Path javaTmpDir = createTemporaryDirectory(String.format("%s-java-tmp-out", tmpDirPrefix));
        Path bazelTmpDir =
                createTemporaryDirectory(String.format("%s-bazel-tmp-out", tmpDirPrefix));

        // Append the JDK from the workspace archive to PATH.
        Joiner joiner = Joiner.on(";").skipNulls();
        String path =
                joiner.join(
                        workspaceDirectory.resolve("prebuilts/jdk/bin").toAbsolutePath().toString(),
                        mEnvironment.get("PATH"));

        List<String> command = new ArrayList<>();

        command.add(workspaceDirectory.resolve("bazelbin").toAbsolutePath().toString());
        command.add(
                String.format(
                        "--server_javabase=%s",
                        workspaceDirectory.resolve("prebuilts/jdk").toAbsolutePath().toString()));
        command.add(
                String.format(
                        "--host_jvm_args=-Djava.io.tmpdir=%s",
                        javaTmpDir.toAbsolutePath().toString()));
        command.add(
                String.format("--output_user_root=%s", bazelTmpDir.toAbsolutePath().toString()));
        command.add(String.format("--max_idle_secs=%d", mBazelMaxIdleTimeout.toSeconds()));

        ProcessBuilder builder = new ProcessBuilder(command);

        builder.environment().put("PATH", path);
        builder.directory(workspaceDirectory.toFile());

        return builder;
    }

    private List<String> listTestTargets(Path workspaceDirectory)
            throws IOException, InterruptedException {
        if (!mTestTargetPatterns.isEmpty()) {
            return mTestTargetPatterns;
        }

        Path logFile = createLogFile(String.format("%s-log", QUERY_TARGETS));

        ProcessBuilder builder = createBazelCommand(workspaceDirectory, QUERY_TARGETS);

        builder.command().add("query");
        builder.command().add("tests(...)");
        builder.redirectError(Redirect.appendTo(logFile.toFile()));

        Process process = startAndWaitForProcess(QUERY_TARGETS, builder, BAZEL_QUERY_TIMEOUT);

        return CharStreams.readLines(new InputStreamReader(process.getInputStream()));
    }

    private void runTests(
            TestInformation testInfo,
            ITestInvocationListener listener,
            List<String> testTargets,
            Path workspaceDirectory)
            throws IOException, InterruptedException {
        Path logFile = createLogFile(String.format("%s-log", RUN_TESTS));

        ProcessBuilder builder = createBazelCommand(workspaceDirectory, RUN_TESTS);

        builder.command().addAll(mBazelStartupOptions);
        builder.command().add("test");
        builder.command().addAll(testTargets);

        for (Map.Entry<String, String> e : getContextTestArgs(testInfo.getContext()).entrySet()) {
            builder.command().add("--test_arg=--invocation-data");
            builder.command().add(String.format("--test_arg=%s=\"%s\"", e.getKey(), e.getValue()));
        }
        builder.command().addAll(mBazelTestExtraArgs);
        builder.redirectErrorStream(true);
        builder.redirectOutput(Redirect.appendTo(logFile.toFile()));

        startAndWaitForProcess(RUN_TESTS, builder, mBazelCommandTimeout);
    }

    private Process startAndWaitForProcess(
            String processTag, ProcessBuilder builder, Duration processTimeout)
            throws InterruptedException, IOException {
        CLog.i("Running command for %s: %s", processTag, new ProcessDebugString(builder));

        Process process = mProcessStarter.start(processTag, builder);
        if (!process.waitFor(processTimeout.toMillis(), TimeUnit.MILLISECONDS)) {
            process.destroy();
            throw new AbortRunException(
                    String.format("%s command timed out.", processTag),
                    FailureStatus.TIMED_OUT,
                    TestErrorIdentifier.TEST_ABORTED);
        }

        if (process.exitValue() != 0) {
            throw new AbortRunException(
                    String.format(
                            "%s command failed. Exit code: %d.", processTag, process.exitValue()),
                    FailureStatus.DEPENDENCY_ISSUE,
                    TestErrorIdentifier.TEST_ABORTED);
        }

        return process;
    }

    private void addTestLogs(ITestLogger logger) {
        for (Path logFile : mLogFiles) {
            try (FileInputStreamSource source = new FileInputStreamSource(logFile.toFile(), true)) {
                logger.testLog(logFile.toFile().getName(), LogDataType.TEXT, source);
            }
        }
    }

    private void cleanup() {
        try {
            MoreFiles.deleteRecursively(mRunTemporaryDirectory);
        } catch (IOException e) {
            CLog.e(e);
        }
    }

    private void copyExtraTradefedJars(Path workspaceDirectory) throws IOException {
        for (File jar : mExtraTradefedJars) {
            Files.copy(
                    jar.toPath(),
                    workspaceDirectory
                            .resolve("tools/tradefederation/core/tradefed/host/framework")
                            .resolve(jar.getName()),
                    StandardCopyOption.REPLACE_EXISTING);
        }
    }

    interface ProcessStarter {
        Process start(String processTag, ProcessBuilder builder) throws IOException;
    }

    private static final class DefaultProcessStarter implements ProcessStarter {
        @Override
        public Process start(String processTag, ProcessBuilder builder) throws IOException {
            return builder.start();
        }
    }

    private Path createTemporaryDirectory(String prefix) throws IOException {
        return Files.createTempDirectory(mRunTemporaryDirectory, prefix);
    }

    private Path createLogFile(String name) throws IOException {
        Path logFile = Files.createTempFile(mRunTemporaryDirectory, name, ".txt");

        mLogFiles.add(logFile);

        return logFile;
    }

    private static FailureDescription throwableToFailureDescription(Exception e) {
        return FailureDescription.create(StreamUtil.getStackTrace(e));
    }

    ImmutableMap<String, String> getContextTestArgs(IInvocationContext context) {
        return ImmutableMap.of(
                "invocation_id",
                context.getAttribute("invocation_id"),
                "work_unit_id",
                context.getAttribute("work_unit_id"));
    }

    private static final class AbortRunException extends RuntimeException {
        private final FailureDescription mFailureDescription;

        public AbortRunException(
                String errorMessage, FailureStatus failureStatus, ErrorIdentifier errorIdentifier) {
            super(errorMessage);
            mFailureDescription =
                    FailureDescription.create(errorMessage, failureStatus)
                            .setErrorIdentifier(errorIdentifier);
        }

        public FailureDescription getFailureDescription() {
            return mFailureDescription;
        }
    }

    private static final class ProcessDebugString {

        private final ProcessBuilder mBuilder;

        ProcessDebugString(ProcessBuilder builder) {
            mBuilder = builder;
        }

        public String toString() {
            return String.join(" ", mBuilder.command());
        }
    }
}
