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
package com.android.atest.toolWindow;

import com.android.atest.AtestUtils;
import com.android.atest.commandAdapter.CommandRunner;
import com.intellij.openapi.wm.ToolWindow;
import com.intellij.openapi.wm.ex.ToolWindowEx;
import org.jetbrains.annotations.NotNull;

import javax.swing.*;
import java.awt.*;

/** UI content of Atest tool window. */
public class AtestToolWindow {

    private static final int INITIAL_WIDTH = 1000;
    private JPanel mAtestToolWindowPanel;
    private JScrollPane mScorll;
    private JTextArea mAtestOutput;
    private JLabel mAtestlabel;
    private JTextField mLunchTarget;
    private JCheckBox mRunOnHost;
    private JCheckBox mTestMapping;
    private JCheckBox mSkipBuild;
    private JButton mRunButton;
    private JComboBox mTestTarget;

    /**
     * Initializes AtestToolWindow with ToolWindow and Project.
     *
     * @param toolWindow a child window of the IDE used to display information.
     * @param basePath a string that represents current project's base path.
     */
    public AtestToolWindow(ToolWindow toolWindow, String basePath) {
        setInitialWidth((ToolWindowEx) toolWindow);
        setRunButton(basePath);
        setTestTarget(basePath);
        mAtestOutput.setMargin(new Insets(0, 10, 0, 0));
    }

    /**
     * Initializes mTestTarget.
     *
     * @param basePath a string that represents current project's base path.
     */
    private void setTestTarget(String basePath) {
        mTestTarget.setEditable(true);
        if (AtestUtils.hasTestMapping(basePath)) {
            mTestTarget.setSelectedItem(basePath);
        }
    }

    /**
     * Sets the initial width of the tool window.
     *
     * @param toolWindowEx a toolWindow which has more methods.
     */
    private void setInitialWidth(@NotNull ToolWindowEx toolWindowEx) {
        int width = toolWindowEx.getComponent().getWidth();
        if (width < INITIAL_WIDTH) {
            toolWindowEx.stretchWidth(INITIAL_WIDTH - width);
        }
    }

    /**
     * Sets the Atest running output to the output area.
     *
     * @param text the output string.
     */
    public void setAtestOutput(String text) {
        mAtestOutput.setText(text);
    }

    /** Initializes the run button. */
    private void setRunButton(String basePath) {
        // When command running, the run button will be set to disable, then the focus will set to
        // next object. Set run button not focusable to prevent it.
        mRunButton.setFocusable(false);
        mRunButton.addActionListener(
                e -> {
                    CommandRunner runner =
                            new CommandRunner(
                                    mLunchTarget.getText(),
                                    mTestTarget.getEditor().getItem().toString(),
                                    AtestUtils.getAndroidRoot(basePath),
                                    AtestToolWindow.this);
                    runner.run();
                });
    }

    /** Scrolls the output window scroll bar to the bottom. */
    public void scrollToEnd() {
        JScrollBar vertical = mScorll.getVerticalScrollBar();
        vertical.setValue(vertical.getMaximum());
    }

    /**
     * Enables (or disables) the run button.
     *
     * @param isEnable true to enable the run button, otherwise disable it.
     */
    public void setRunEnable(boolean isEnable) {
        mRunButton.setEnabled(isEnable);
    }

    /**
     * Gets the UI panel of Atest tool window.
     *
     * @return the JPanel of Atest tool window.
     */
    public JPanel getContent() {
        return mAtestToolWindowPanel;
    }
}
