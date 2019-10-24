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

import com.intellij.openapi.wm.ToolWindow;

import javax.swing.*;

/** UI content of Atest tool window. */
public class AtestToolWindow {

    private JPanel AtestToolWindowPanel;
    private JScrollPane scorll;
    private JTextArea atestOutput;
    private JLabel atest;
    private JTextField target;
    private JCheckBox runOnHost;
    private JCheckBox Test_mapping;
    private JCheckBox skipBuild;
    private JButton run;
    private JComboBox comboBox1;

    public AtestToolWindow(ToolWindow toolWindow) {}

    /**
     * Sets the Atest running output to the output area.
     *
     * @param text the output string.
     */
    public void setAtestOutput(String text) {
        atestOutput.setText(text);
    }

    /** Scrolls the output window scroll bar to the bottom. */
    public void scrollToEnd() {
        JScrollBar vertical = scorll.getVerticalScrollBar();
        vertical.setValue(vertical.getMaximum());
    }

    /**
     * Gets the UI panel of Atest tool window.
     *
     * @return the JPanel of Atest tool window.
     */
    public JPanel getContent() {
        return AtestToolWindowPanel;
    }
}
