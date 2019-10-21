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
package com.android.atest.commandAdapter;

import com.android.atest.toolWindow.AtestToolWindow;
import com.intellij.execution.ExecutionException;
import com.intellij.execution.configurations.GeneralCommandLine;
import com.intellij.execution.process.ColoredProcessHandler;
import com.intellij.execution.process.ProcessListener;
import com.intellij.openapi.diagnostic.Logger;

import java.nio.charset.Charset;
import java.util.ArrayList;

/** A manager to handle command. */
public class CommandRunner {

    private static final Logger LOG = Logger.getInstance(CommandRunner.class);
    private GeneralCommandLine mCommand;
    private ProcessListener mProcessListener;

    public CommandRunner(ArrayList<String> cmds, String workPath) {
        mCommand = new GeneralCommandLine(cmds);
        mCommand.setCharset(Charset.forName("UTF-8"));
        mCommand.setWorkDirectory(workPath);
    }

    /**
     * Set the process listener.
     *
     * @param processListener a processListener handle the output.
     */
    public void setProcessListener(ProcessListener processListener) {
        mProcessListener = processListener;
    }

    /**
     * Set the process listener by tool window.
     *
     * <p>Because we use Atest tool window to display the command output, this function generates
     * process listener by Atest tool window.
     *
     * @param toolWindow an AtestToolWindow to display the output.
     */
    public void setProcessListener(AtestToolWindow toolWindow) {
        mProcessListener = new AtestProcessListener(toolWindow);
    }

    /**
     * Execute the command in processHandler.
     *
     * <p>Execute this method when caller is ready to access linux command.
     */
    public void run() {
        try {
            ColoredProcessHandler processHandler = new ColoredProcessHandler(mCommand);
            if (mProcessListener != null) {
                processHandler.addProcessListener(mProcessListener);
            }
            processHandler.startNotify();
        } catch (ExecutionException e) {
            e.printStackTrace();
            // TODO(b/142692007): Use dialog to inform users the fatal error.
            LOG.error("Command executes fail: " + mCommand.getCommandLineString());
        }
    }
}
