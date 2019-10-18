/*
 * Copyright (C) 2019 The Android Open Source Project
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
package com.android.atest.run;

import com.intellij.execution.ExecutionException;
import com.intellij.execution.Executor;
import com.intellij.execution.configurations.ConfigurationFactory;
import com.intellij.execution.configurations.LocatableConfigurationBase;
import com.intellij.execution.configurations.RunConfiguration;
import com.intellij.execution.configurations.RunProfileState;
import com.intellij.execution.configurations.RuntimeConfigurationException;
import com.intellij.execution.runners.ExecutionEnvironment;
import com.intellij.openapi.options.SettingsEditor;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.util.InvalidDataException;
import org.jdom.Element;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;

/** Runs configurations which can be managed by a user and displayed in the UI. */
public class AtestRunConfiguration extends LocatableConfigurationBase {

    protected AtestRunConfiguration(Project project, ConfigurationFactory factory, String name) {
        super(project, factory, name);
    }

    /**
     * Reads the run configuration settings from the file system.
     *
     * @param element an Element object to read.
     * @throws InvalidDataException if the data is invalid.
     */
    @Override
    public void readExternal(@NotNull Element element) throws InvalidDataException {}

    /**
     * Stores the run configuration settings at file system.
     *
     * @param element an Element object to write.
     */
    @Override
    public void writeExternal(@NotNull Element element) {}

    /**
     * Returns the UI control for editing the run configuration settings. If additional control over
     * validation is required, the object returned from this method may also implement {@link
     * com.intellij.execution.impl.CheckableRunConfigurationEditor}. The returned object can also
     * implement {@link com.intellij.openapi.options.SettingsEditorGroup} if the settings it
     * provides need to be displayed in multiple tabs.
     *
     * @return Atest settings editor component.
     */
    @NotNull
    @Override
    public SettingsEditor<? extends RunConfiguration> getConfigurationEditor() {
        return new AtestSettingsEditor();
    }

    /**
     * Checks whether the run configuration settings are valid. Note that this check may be invoked
     * on every change (i.e. after each character typed in an input field).
     *
     * @throws RuntimeConfigurationException if the configuration settings contain a non-fatal
     *     problem which the user should be warned about but the execution should still be allowed.
     */
    @Override
    public void checkConfiguration() throws RuntimeConfigurationException {
        super.checkConfiguration();
    }

    /**
     * Prepares for executing a specific instance of the run configuration.
     *
     * @param executor the execution mode selected by the user (run, debug, profile etc.)
     * @param executionEnvironment the environment object containing additional settings for
     *     executing the configuration.
     * @throws ExecutionException if exception happens when executing.
     * @return the RunProfileState describing the process which is about to be started, or null if
     *     it's impossible to start the process.
     */
    @Nullable
    @Override
    public RunProfileState getState(
            @NotNull Executor executor, @NotNull ExecutionEnvironment executionEnvironment)
            throws ExecutionException {
        return null;
    }
}
