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
import com.android.tradefed.invoker.TestInformation;
import com.android.tradefed.log.ITestLogger;
import com.android.tradefed.log.LogUtil.CLog;
import com.android.tradefed.result.FailureDescription;
import com.android.tradefed.result.FileInputStreamSource;
import com.android.tradefed.result.ITestInvocationListener;
import com.android.tradefed.result.LogDataType;
import com.android.tradefed.result.error.ErrorIdentifier;
import com.android.tradefed.result.error.TestErrorIdentifier;
import com.android.tradefed.result.proto.LogFileProto.LogFileInfo;
import com.android.tradefed.result.proto.ProtoResultParser;
import com.android.tradefed.result.proto.TestRecordProto.ChildReference;
import com.android.tradefed.result.proto.TestRecordProto.FailureStatus;
import com.android.tradefed.result.proto.TestRecordProto.TestRecord;
import com.android.tradefed.testtype.IRemoteTest;
import com.android.tradefed.util.ZipUtil;
import com.android.tradefed.util.proto.TestRecordProtoUtil;

import com.google.common.base.Throwables;
import com.google.common.collect.SetMultimap;
import com.google.common.collect.HashMultimap;
import com.google.common.io.CharStreams;
import com.google.common.io.MoreFiles;
import com.google.devtools.build.lib.buildeventstream.BuildEventStreamProtos;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;

import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.lang.ProcessBuilder.Redirect;
import java.net.URI;
import java.net.URISyntaxException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Map.Entry;
import java.util.Properties;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;
import java.util.zip.ZipFile;

/** Test runner for executing Bazel tests. */
@OptionClass(alias = "bazel-test")
public final class BazelTest implements IRemoteTest {

    public static final String QUERY_TARGETS = "query_targets";
    public static final String RUN_TESTS = "run_tests";
    // TODO(b/275407694): Use the module_name parameter to filter tests instead of the query
    // command.
    public static final String TEST_QUERY_TEMPLATE = "attr(module_name, \"(?:%s)\", %s)";

    // Add method excludes to TF's global filters since Bazel doesn't support target-specific
    // arguments. See https://github.com/bazelbuild/rules_go/issues/2784.
    // TODO(b/274787592): Integrate with Bazel's test filtering to filter specific test cases.
    public static final String GLOBAL_EXCLUDE_FILTER_TEMPLATE =
            "--test_arg=--global-filters:exclude-filter=%s";

    private static final Duration BAZEL_QUERY_TIMEOUT = Duration.ofMinutes(5);
    private static final String TEST_NAME = BazelTest.class.getName();
    // Bazel internally calls the test output archive file "test.outputs__outputs.zip", the double
    // underscore is part of this name.
    private static final String TEST_UNDECLARED_OUTPUTS_ARCHIVE_NAME = "test.outputs__outputs.zip";
    private static final String PROTO_RESULTS_FILE_NAME = "proto-results";

    private final List<Path> mTemporaryPaths = new ArrayList<>();
    private final List<Path> mLogFiles = new ArrayList<>();
    private final Properties mProperties;
    private final ProcessStarter mProcessStarter;
    private final Path mTemporaryDirectory;
    private final ExecutorService mExecutor;

    private Path mRunTemporaryDirectory;

    private enum FilterType {
        MODULE,
        TEST_CASE
    };

    @Option(
            name = "bazel-test-command-timeout",
            description = "Timeout for running the Bazel test.")
    private Duration mBazelCommandTimeout = Duration.ofHours(1L);

    @Option(
            name = "bazel-test-suite-root-dir",
            description =
                    "Name of the environment variable set by CtsTestLauncher indicating the"
                            + " location of the root bazel-test-suite dir.")
    private String mSuiteRootDirEnvVar = "BAZEL_SUITE_ROOT";

    @Option(
            name = "bazel-startup-options",
            description = "List of startup options to be passed to Bazel.")
    private final List<String> mBazelStartupOptions = new ArrayList<>();

    @Option(
            name = "bazel-test-extra-args",
            description = "List of extra arguments to be passed to Bazel")
    private final List<String> mBazelTestExtraArgs = new ArrayList<>();

    @Option(
            name = "bazel-max-idle-timout",
            description = "Max idle timeout in seconds for bazel commands.")
    private Duration mBazelMaxIdleTimeout = Duration.ofSeconds(5L);

    @Option(name = "exclude-filter", description = "Test modules to exclude when running tests.")
    private final List<String> mExcludeTargets = new ArrayList<>();

    @Option(name = "include-filter", description = "Test modules to include when running tests.")
    private final List<String> mIncludeTargets = new ArrayList<>();

    @Option(
            name = "report-cached-test-results",
            description = "Whether or not to report cached test results.")
    private boolean mReportCachedTestResults = true;

    public BazelTest() {
        this(new DefaultProcessStarter(), System.getProperties());
    }

    @VisibleForTesting
    BazelTest(ProcessStarter processStarter, Properties properties) {
        mProcessStarter = processStarter;
        mExecutor = Executors.newFixedThreadPool(1);
        mProperties = properties;
        mTemporaryDirectory = Paths.get(properties.getProperty("java.io.tmpdir"));
    }

    @Override
    public void run(TestInformation testInfo, ITestInvocationListener listener)
            throws DeviceNotAvailableException {

        List<FailureDescription> runFailures = new ArrayList<>();
        long startTime = System.currentTimeMillis();

        try {
            initialize();
            runTestsAndParseResults(testInfo, listener, runFailures);
        } catch (AbortRunException e) {
            runFailures.add(e.getFailureDescription());
        } catch (IOException | InterruptedException e) {
            runFailures.add(throwableToTestFailureDescription(e));
        }

        listener.testModuleStarted(testInfo.getContext());
        listener.testRunStarted(TEST_NAME, 0);
        reportRunFailures(runFailures, listener);
        listener.testRunEnded(System.currentTimeMillis() - startTime, Collections.emptyMap());
        listener.testModuleEnded();

        addTestLogs(listener);
        cleanup();
    }

    private void initialize() throws IOException {
        mRunTemporaryDirectory = Files.createTempDirectory(mTemporaryDirectory, "bazel-test-");
    }

    private void runTestsAndParseResults(
            TestInformation testInfo,
            ITestInvocationListener listener,
            List<FailureDescription> runFailures)
            throws IOException, InterruptedException {

        Path workspaceDirectory = resolveWorkspacePath();

        List<String> testTargets = listTestTargets(workspaceDirectory);
        if (testTargets.isEmpty()) {
            throw new AbortRunException(
                    "No targets found, aborting",
                    FailureStatus.DEPENDENCY_ISSUE,
                    TestErrorIdentifier.TEST_ABORTED);
        }

        Path bepFile = createTemporaryFile("BEP_output");

        Process bazelTestProcess =
                startTests(testInfo, listener, testTargets, workspaceDirectory, bepFile);
        Future<?> testResult;
        try (BepFileTailer tailer = BepFileTailer.create(bepFile)) {
            testResult =
                    mExecutor.submit(
                            () -> {
                                try {
                                    waitForProcess(
                                            bazelTestProcess, RUN_TESTS, mBazelCommandTimeout);
                                } catch (InterruptedException e) {
                                    Thread.currentThread().interrupt();
                                    throw new AbortRunException(
                                            "Bazel Test process interrupted",
                                            FailureStatus.TEST_FAILURE,
                                            TestErrorIdentifier.TEST_ABORTED);
                                } finally {
                                    tailer.stop();
                                }
                            });

            reportTestResults(listener, testInfo, runFailures, tailer);
        }

        try {
            testResult.get();
        } catch (ExecutionException e) {
            Throwables.throwIfUnchecked(e.getCause());
        }
    }

    void reportTestResults(
            ITestInvocationListener listener,
            TestInformation testInfo,
            List<FailureDescription> runFailures,
            BepFileTailer tailer)
            throws InterruptedException, IOException {

        ProtoResultParser resultParser =
                new ProtoResultParser(listener, testInfo.getContext(), false, "tf-test-process-");
        resultParser.setQuiet(false);

        BuildEventStreamProtos.BuildEvent event;
        while ((event = tailer.nextEvent()) != null) {
            if (event.getLastMessage()) {
                return;
            }

            if (!event.hasTestResult()) {
                continue;
            }

            if (!mReportCachedTestResults && isTestResultCached(event.getTestResult())) {
                continue;
            }

            try {
                reportEventsInTestOutputsArchive(event.getTestResult(), resultParser);
            } catch (IOException | InterruptedException | URISyntaxException e) {
                runFailures.add(
                        throwableToInfraFailureDescription(e)
                                .setErrorIdentifier(TestErrorIdentifier.OUTPUT_PARSER_ERROR));
            }
        }

        throw new AbortRunException(
                "Unexpectedly hit end of BEP file without receiving last message",
                FailureStatus.INFRA_FAILURE,
                TestErrorIdentifier.OUTPUT_PARSER_ERROR);
    }

    private static boolean isTestResultCached(BuildEventStreamProtos.TestResult result) {
        return result.getCachedLocally() || result.getExecutionInfo().getCachedRemotely();
    }

    private ProcessBuilder createBazelCommand(Path workspaceDirectory, String tmpDirPrefix)
            throws IOException {

        Path javaTmpDir = createTemporaryDirectory(String.format("%s-java-tmp-out", tmpDirPrefix));
        Path bazelTmpDir =
                createTemporaryDirectory(String.format("%s-bazel-tmp-out", tmpDirPrefix));

        List<String> command = new ArrayList<>();

        command.add(workspaceDirectory.resolve("bazel.sh").toAbsolutePath().toString());
        command.add(
                String.format(
                        "--host_jvm_args=-Djava.io.tmpdir=%s",
                        javaTmpDir.toAbsolutePath().toString()));
        command.add(
                String.format("--output_user_root=%s", bazelTmpDir.toAbsolutePath().toString()));
        command.add(String.format("--max_idle_secs=%d", mBazelMaxIdleTimeout.toSeconds()));

        ProcessBuilder builder = new ProcessBuilder(command);

        builder.directory(workspaceDirectory.toFile());

        return builder;
    }

    private List<String> listTestTargets(Path workspaceDirectory)
            throws IOException, InterruptedException {

        Path logFile = createLogFile(String.format("%s-log", QUERY_TARGETS));

        ProcessBuilder builder = createBazelCommand(workspaceDirectory, QUERY_TARGETS);

        builder.command().add("query");
        builder.command().add(buildQueryString());
        builder.redirectError(Redirect.appendTo(logFile.toFile()));

        Process process = startAndWaitForProcess(QUERY_TARGETS, builder, BAZEL_QUERY_TIMEOUT);

        return CharStreams.readLines(new InputStreamReader(process.getInputStream()));
    }

    private String buildQueryString() {
        String allTestsSelector = "tests(...)";
        StringBuilder query = new StringBuilder();
        Collection<String> moduleExcludes =
                groupTargetsByType(mExcludeTargets).get(FilterType.MODULE);
        Collection<String> moduleIncludes =
                groupTargetsByType(mIncludeTargets).get(FilterType.MODULE);

        if (!moduleIncludes.isEmpty() && !moduleExcludes.isEmpty()) {
            throw new AbortRunException(
                    "Invalid options: cannot set both module-level include filters and module-level"
                            + " exclude filters.",
                    FailureStatus.DEPENDENCY_ISSUE,
                    TestErrorIdentifier.TEST_ABORTED);
        }

        if (!moduleIncludes.isEmpty()) {
            query.append(
                    String.format(
                            TEST_QUERY_TEMPLATE,
                            String.join("|", moduleIncludes),
                            allTestsSelector));
        } else if (!moduleExcludes.isEmpty()) {
            query.append(allTestsSelector + " - ");
            query.append(
                    String.format(
                            TEST_QUERY_TEMPLATE,
                            String.join("|", moduleExcludes),
                            allTestsSelector));
        } else {
            query.append(allTestsSelector);
        }

        return query.toString();
    }

    private Process startTests(
            TestInformation testInfo,
            ITestInvocationListener listener,
            List<String> testTargets,
            Path workspaceDirectory,
            Path bepFile)
            throws IOException {

        Path logFile = createLogFile(String.format("%s-log", RUN_TESTS));

        ProcessBuilder builder = createBazelCommand(workspaceDirectory, RUN_TESTS);

        builder.command().addAll(mBazelStartupOptions);
        builder.command().add("test");
        builder.command().addAll(testTargets);

        builder.command()
                .add(String.format("--build_event_binary_file=%s", bepFile.toAbsolutePath()));

        builder.command().addAll(mBazelTestExtraArgs);

        Collection<String> testFilters =
                groupTargetsByType(mExcludeTargets).get(FilterType.TEST_CASE);
        for (String test : testFilters) {
            builder.command().add(String.format(GLOBAL_EXCLUDE_FILTER_TEMPLATE, test));
        }
        builder.redirectErrorStream(true);
        builder.redirectOutput(Redirect.appendTo(logFile.toFile()));

        return startProcess(RUN_TESTS, builder);
    }

    private static SetMultimap<FilterType, String> groupTargetsByType(List<String> targets) {
        Map<FilterType, List<String>> groupedMap =
                targets.stream()
                        .collect(
                                Collectors.groupingBy(
                                        s ->
                                                s.contains(" ")
                                                        ? FilterType.TEST_CASE
                                                        : FilterType.MODULE));

        SetMultimap<FilterType, String> groupedMultiMap = HashMultimap.create();
        for (Entry<FilterType, List<String>> entry : groupedMap.entrySet()) {
            groupedMultiMap.putAll(entry.getKey(), entry.getValue());
        }

        return groupedMultiMap;
    }

    private Process startAndWaitForProcess(
            String processTag, ProcessBuilder builder, Duration processTimeout)
            throws InterruptedException, IOException {

        Process process = startProcess(processTag, builder);

        waitForProcess(process, processTag, processTimeout);

        return process;
    }

    private Process startProcess(String processTag, ProcessBuilder builder) throws IOException {

        CLog.i("Running command for %s: %s", processTag, new ProcessDebugString(builder));

        return mProcessStarter.start(processTag, builder);
    }

    private void waitForProcess(Process process, String processTag, Duration processTimeout)
            throws InterruptedException {
        if (!process.waitFor(processTimeout.toMillis(), TimeUnit.MILLISECONDS)) {
            process.destroy();
            throw new AbortRunException(
                    String.format("%s command timed out", processTag),
                    FailureStatus.TIMED_OUT,
                    TestErrorIdentifier.TEST_ABORTED);
        }

        if (process.exitValue() != 0) {
            throw new AbortRunException(
                    String.format(
                            "%s command failed. Exit code: %d", processTag, process.exitValue()),
                    FailureStatus.DEPENDENCY_ISSUE,
                    TestErrorIdentifier.TEST_ABORTED);
        }
    }


    private void reportEventsInTestOutputsArchive(
            BuildEventStreamProtos.TestResult result, ProtoResultParser resultParser)
            throws IOException, InvalidProtocolBufferException, InterruptedException,
                    URISyntaxException {

        BuildEventStreamProtos.File outputsFile =
                result.getTestActionOutputList().stream()
                        .filter(file -> file.getName().equals(TEST_UNDECLARED_OUTPUTS_ARCHIVE_NAME))
                        .findAny()
                        .orElseThrow(() -> new IOException("No test output archive found"));

        URI uri = new URI(outputsFile.getUri());

        File zipFile = new File(uri.getPath());
        Path outputFilesDir = Files.createTempDirectory(mRunTemporaryDirectory, "output_zip-");

        try {
            ZipUtil.extractZip(new ZipFile(zipFile), outputFilesDir.toFile());

            File protoResult = outputFilesDir.resolve(PROTO_RESULTS_FILE_NAME).toFile();
            TestRecord record = TestRecordProtoUtil.readFromFile(protoResult);

            TestRecord.Builder recordBuilder = record.toBuilder();
            recursivelyUpdateArtifactsRootPath(recordBuilder, outputFilesDir);
            moveRootRecordArtifactsToFirstChild(recordBuilder);
            resultParser.processFinalizedProto(recordBuilder.build());
        } finally {
            MoreFiles.deleteRecursively(outputFilesDir);
        }
    }

    private void recursivelyUpdateArtifactsRootPath(TestRecord.Builder recordBuilder, Path newRoot)
            throws InvalidProtocolBufferException {

        Map<String, Any> updatedMap = new HashMap<>();
        for (Entry<String, Any> entry : recordBuilder.getArtifactsMap().entrySet()) {
            LogFileInfo info = entry.getValue().unpack(LogFileInfo.class);

            Path relativePath = findRelativeArtifactPath(Paths.get(info.getPath()));

            LogFileInfo updatedInfo =
                    info.toBuilder()
                            .setPath(newRoot.resolve(relativePath).toAbsolutePath().toString())
                            .build();
            updatedMap.put(entry.getKey(), Any.pack(updatedInfo));
        }

        recordBuilder.putAllArtifacts(updatedMap);

        for (ChildReference.Builder childBuilder : recordBuilder.getChildrenBuilderList()) {
            recursivelyUpdateArtifactsRootPath(childBuilder.getInlineTestRecordBuilder(), newRoot);
        }
    }

    private Path findRelativeArtifactPath(Path originalPath) {
        // The log files are stored under
        // ${EXTRACTED_UNDECLARED_OUTPUTS}/stub/-1/stub/inv_xxx/inv_xxx/logfile so the new path is
        // found by trimming down the original path until it starts with "stub/-1/stub" and
        // appending that to our extracted directory.
        // TODO(b/251279690) Create a directory within undeclared outputs which we can more
        // reliably look for to calculate this relative path.
        Path delimiter = Paths.get("stub/-1/stub");

        Path relativePath = originalPath;
        while (!relativePath.startsWith(delimiter)
                && relativePath.getNameCount() > delimiter.getNameCount()) {
            relativePath = relativePath.subpath(1, relativePath.getNameCount());
        }

        if (!relativePath.startsWith(delimiter)) {
            throw new IllegalArgumentException(
                    String.format(
                            "Artifact path '%s' does not contain delimiter '%s' and therefore"
                                    + " cannot be found",
                            originalPath, delimiter));
        }

        return relativePath;
    }

    private void moveRootRecordArtifactsToFirstChild(TestRecord.Builder recordBuilder) {
        if (recordBuilder.getChildrenCount() == 0) {
            return;
        }

        TestRecord.Builder childTestRecordBuilder =
                recordBuilder.getChildrenBuilder(0).getInlineTestRecordBuilder();
        for (Entry<String, Any> entry : recordBuilder.getArtifactsMap().entrySet()) {
            childTestRecordBuilder.putArtifacts(entry.getKey(), entry.getValue());
        }

        recordBuilder.clearArtifacts();
    }

    private void reportRunFailures(
            List<FailureDescription> runFailures, ITestInvocationListener listener) {

        if (runFailures.isEmpty()) {
            return;
        }

        for (FailureDescription runFailure : runFailures) {
            CLog.e(runFailure.getErrorMessage());
        }

        FailureDescription reportedFailure = runFailures.get(0);
        listener.testRunFailed(
                FailureDescription.create(
                                String.format(
                                        "The run had %d failures, the first of which was: %s\n"
                                                + "See the subprocess-host_log for more details.",
                                        runFailures.size(), reportedFailure.getErrorMessage()),
                                reportedFailure.getFailureStatus())
                        .setErrorIdentifier(reportedFailure.getErrorIdentifier()));
    }

    private Path resolveWorkspacePath() {
        String suiteRootPath = mProperties.getProperty(mSuiteRootDirEnvVar);
        if (suiteRootPath == null || suiteRootPath.isEmpty()) {
            throw new AbortRunException(
                    "Bazel Test Suite root directory not set, aborting",
                    FailureStatus.DEPENDENCY_ISSUE,
                    TestErrorIdentifier.TEST_ABORTED);
        }

        // TODO(b/233885171): Remove resolve once workspace archive is updated.
        return Paths.get(suiteRootPath).resolve("android-bazel-suite/out/atest_bazel_workspace");
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

    private Path createTemporaryFile(String prefix) throws IOException {
        return Files.createTempFile(mRunTemporaryDirectory, prefix, "");
    }

    private Path createLogFile(String name) throws IOException {
        Path logFile = Files.createTempFile(mRunTemporaryDirectory, name, ".txt");

        mLogFiles.add(logFile);

        return logFile;
    }

    private static FailureDescription throwableToTestFailureDescription(Throwable t) {
        return FailureDescription.create(t.getMessage())
                .setCause(t)
                .setFailureStatus(FailureStatus.TEST_FAILURE);
    }

    private static FailureDescription throwableToInfraFailureDescription(Exception e) {
        return FailureDescription.create(e.getMessage())
                .setCause(e)
                .setFailureStatus(FailureStatus.INFRA_FAILURE);
    }

    private static final class AbortRunException extends RuntimeException {
        private final FailureDescription mFailureDescription;

        public AbortRunException(
                String errorMessage, FailureStatus failureStatus, ErrorIdentifier errorIdentifier) {
            this(
                    FailureDescription.create(errorMessage, failureStatus)
                            .setErrorIdentifier(errorIdentifier));
        }

        public AbortRunException(FailureDescription failureDescription) {
            super(failureDescription.getErrorMessage());
            mFailureDescription = failureDescription;
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
