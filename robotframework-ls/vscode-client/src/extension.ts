/*
Original work Copyright (c) Microsoft Corporation (MIT)
See ThirdPartyNotices.txt in the project root for license information.
All modifications Copyright (c) Robocorp Technologies Inc.
All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License")
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

	http: // www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

'use strict';

import * as net from 'net';
import * as path from 'path';
import * as fs from 'fs';

import { workspace, Disposable, ExtensionContext, window, commands, ConfigurationTarget, debug, DebugAdapterExecutable, ProviderResult, DebugConfiguration, WorkspaceFolder, CancellationToken, DebugConfigurationProvider, DebugSession, DebugSessionOptions } from 'vscode';
import { LanguageClient, LanguageClientOptions, ServerOptions } from 'vscode-languageclient';
import { ProgressReport, handleProgressMessage } from './progress';
import { Timing } from './time';


import * as vscode from 'vscode';

const OUTPUT_CHANNEL_NAME = "Robot Framework";
const OUTPUT_CHANNEL = window.createOutputChannel(OUTPUT_CHANNEL_NAME);

function createClientOptions(initializationOptions: object): LanguageClientOptions {
	const clientOptions: LanguageClientOptions = {
		documentSelector: ["robotframework"],
		synchronize: {
			configurationSection: ["robot", "robocorp.home"]
		},
		outputChannel: OUTPUT_CHANNEL,
		initializationOptions: initializationOptions,
	}
	return clientOptions;
}

function startLangServerIO(command: string, args: string[], initializationOptions: object): LanguageClient {
	const serverOptions: ServerOptions = {
		command,
		args,
	};
	// See: https://code.visualstudio.com/api/language-extensions/language-server-extension-guide
	return new LanguageClient(command, serverOptions, createClientOptions(initializationOptions));
}

function startLangServerTCP(addr: number, initializationOptions: object): LanguageClient {
	const serverOptions: ServerOptions = function () {
		return new Promise((resolve, reject) => {
			var client = new net.Socket();
			client.connect(addr, "127.0.0.1", function () {
				resolve({
					reader: client,
					writer: client
				});
			});
		});
	}
	return new LanguageClient(`tcp lang server (port ${addr})`, serverOptions, createClientOptions(initializationOptions));
}

function findExecutableInPath(executable: string) {
	const IS_WINDOWS = process.platform == "win32";
	const sep = IS_WINDOWS ? ";" : ":";
	const PATH = process.env["PATH"];
	const split = PATH.split(sep);
	for (let i = 0; i < split.length; i++) {
		const s = path.join(split[i], executable);
		if (fs.existsSync(s)) {
			return s;
		}
	}
	return undefined;
}

class RobotDebugConfigurationProvider implements DebugConfigurationProvider {

	provideDebugConfigurations?(folder: WorkspaceFolder | undefined, token?: CancellationToken): DebugConfiguration[] {
		let configurations: DebugConfiguration[] = [];
		configurations.push({
			"type": "robotframework-lsp",
			"name": "Robot Framework: Launch .robot file",
			"request": "launch",
			"cwd": "^\"\\${workspaceFolder}\"",
			"target": "^\"\\${file}\"",
			"terminal": "none",
			"env": {},
			"args": []
		});
		return configurations;
	};

	async resolveDebugConfigurationWithSubstitutedVariables(folder: WorkspaceFolder | undefined, debugConfiguration: DebugConfiguration, token?: CancellationToken): Promise<DebugConfiguration> {
		// When we resolve a configuration we add the pythonpath and variables to the command line.
		let args: Array<string> = debugConfiguration.args;
		let config = workspace.getConfiguration("robot");
		let pythonpath: Array<string> = config.get<Array<string>>("pythonpath");
		
		let variables: object = config.get("variables");
		let targetRobot: object = debugConfiguration.target;

		// If it's not specified in the language, let's check if some plugin wants to provide an implementation.
		let interpreter: InterpreterInfo = await commands.executeCommand('robot.resolveInterpreter', targetRobot);
		if (interpreter) {
			pythonpath = pythonpath.concat(interpreter.additionalPythonpathEntries);

			if (interpreter.environ) {
				if (!debugConfiguration.env) {
					debugConfiguration.env = interpreter.environ;
				} else {
					for (let key of Object.keys(interpreter.environ)) {
						debugConfiguration.env[key] = interpreter.environ[key];
					}
				}
			}
		}

		let newArgs = [];
		pythonpath.forEach(element => {
			newArgs.push('--pythonpath');
			newArgs.push(element);
		});

		for (let key in variables) {
			if (variables.hasOwnProperty(key)) {
				newArgs.push('--variable');
				newArgs.push(key + ':' + variables[key]);
			}
		}
		if (args) {
			args = args.concat(newArgs);
		} else {
			args = newArgs;
		}
		debugConfiguration.args = args;
		return debugConfiguration;
	};
}

interface InterpreterInfo {
	pythonExe: string;
	environ?: { [key: string]: string };
	additionalPythonpathEntries: string[];
}


function registerDebugger(languageServerExecutable: string) {
	async function createDebugAdapterExecutable(env: { [key: string]: string }, targetRobot: string): Promise<DebugAdapterExecutable> {
		let config = workspace.getConfiguration("robot");
		let dapPythonExecutable: string = config.get<string>("python.executable");

		// If it's not specified in the language, let's check if some plugin wants to provide an implementation.
		let interpreter: InterpreterInfo = await commands.executeCommand('robot.resolveInterpreter', targetRobot);
		if (interpreter) {
			dapPythonExecutable = interpreter.pythonExe;
			if (interpreter.environ) {
				if (!env) {
					env = interpreter.environ;
				} else {
					for (let key of Object.keys(interpreter.environ)) {
						env[key] = interpreter.environ[key];
					}
				}
			}
		}

		if (!dapPythonExecutable) {
			// If the dapPythonExecutable is not specified, use the default language server executable.
			if (!languageServerExecutable) {
				window.showWarningMessage('Error getting language server python executable for creating a debug adapter.');
				return;
			}
			dapPythonExecutable = languageServerExecutable;
		}

		let targetMain: string = path.resolve(__dirname, '../../src/robotframework_debug_adapter/__main__.py');
		if (!fs.existsSync(targetMain)) {
			window.showWarningMessage('Error. Expected: ' + targetMain + " to exist.");
			return;
		}
		if (!fs.existsSync(dapPythonExecutable)) {
			window.showWarningMessage('Error. Expected: ' + dapPythonExecutable + " to exist.");
			return;
		}
		if (env) {
			return new DebugAdapterExecutable(dapPythonExecutable, ['-u', targetMain], { "env": env });

		} else {
			return new DebugAdapterExecutable(dapPythonExecutable, ['-u', targetMain]);
		}
	};


	debug.registerDebugAdapterDescriptorFactory('robotframework-lsp', {
		createDebugAdapterDescriptor: session => {
			let env = session.configuration.env;
			let target = session.configuration.target;
			return createDebugAdapterExecutable(env, target);
		}
	});

	debug.registerDebugConfigurationProvider('robotframework-lsp', new RobotDebugConfigurationProvider());
}


interface ExecutableAndMessage {
	executable: string;
	message: string;
}


async function getDefaultLanguageServerPythonExecutable(): Promise<ExecutableAndMessage> {
	OUTPUT_CHANNEL.appendLine("Getting language server Python executable.");
	let config = workspace.getConfiguration("robot");
	let languageServerPython: string = config.get<string>("language-server.python");
	let executable: string = languageServerPython;

	if (!executable || (executable.indexOf('/') == -1 && executable.indexOf('\\') == -1)) {
		// Try to use the Robocorp Code extension to provide one for us (if it's installed and
		// available).
		try {
			let languageServerPython: string = await commands.executeCommand<string>(
				"robocorp.getLanguageServerPython");
			if (languageServerPython) {
				OUTPUT_CHANNEL.appendLine("Language server Python executable gotten from robocorp.getLanguageServerPython.");
				return {
					executable: languageServerPython,
					'message': undefined
				};
			}
		} catch (error) {
			// The command may not be available (in this case, go forward and try to find it in the filesystem).
		}

		// Search python from the path.
		if (!executable) {
			OUTPUT_CHANNEL.appendLine("Language server Python executable. Searching in PATH.");
			if (process.platform == "win32") {
				executable = findExecutableInPath("python.exe");
			} else {
				executable = findExecutableInPath("python3");
				if (!fs.existsSync(executable)) {
					executable = findExecutableInPath("python");
				}
			}
		} else {
			OUTPUT_CHANNEL.appendLine("Language server Python executable. Searching " + executable + " from the PATH.");
			executable = findExecutableInPath(executable);
			OUTPUT_CHANNEL.appendLine("Language server Python executable. Found: " + executable);
		}
		if (!fs.existsSync(executable)) {
			return {
				executable: undefined,
				'message': 'Unable to start robotframework-lsp because: python could not be found on the PATH. Do you want to select a python executable to start robotframework-lsp?'
			};
		}
		return {
			executable: executable,
			'message': undefined
		};

	} else {
		if (!fs.existsSync(executable)) {
			return {
				executable: undefined,
				'message': 'Unable to start robotframework-lsp because: ' + executable + ' does not exist. Do you want to select a new python executable to start robotframework-lsp?'
			};
		}
		return {
			executable: executable,
			'message': undefined
		};
	}
}

function debugSuiteOrTestcase(document_uri: string, testcase?: string, options?: DebugSessionOptions) {
	return new Promise((res, rej) => {
		let config = workspace.getConfiguration("robot");
		let pythonenv: object = config.get("python.env");

		let uri = vscode.Uri.parse(document_uri);

		let folder = workspace.getWorkspaceFolder(uri);

		var args = [
			
		]

		if (testcase) {
			args.push("-t")
			args.push(testcase)
		}

		debug.startDebugging(folder, {
			type: "robotframework-lsp",
			name: `Robotframework: Suite: ${document_uri}${testcase ? " Testcase: " + testcase: ""}`,
			request: "launch",
			cwd: folder.uri.fsPath,
			target: uri.fsPath,
			terminal: "none",
			env: pythonenv,
			args: args
		}, options).then(res, rej);

	});
}

function runTestcase(document_uri: string, testcase: string) {
	return debugSuiteOrTestcase(document_uri, testcase)
}

function debugTestcase(document_uri: string, testcase: string) {
	return debugSuiteOrTestcase(document_uri, testcase)
}

function runTestsuite(document_uri: string) {
	return debugSuiteOrTestcase(document_uri, null, {noDebug: true})
}

function debugTestsuite(document_uri: string) {
	return debugSuiteOrTestcase(document_uri)
}


export async function activate(context: ExtensionContext) {
	try {
		// The first thing we need is the python executable.
		let timing = new Timing();
		let executableAndMessage = await getDefaultLanguageServerPythonExecutable();
		if (executableAndMessage.message) {
			OUTPUT_CHANNEL.appendLine(executableAndMessage.message);

			let saveInUser: string = 'Yes (save in user settings)';
			let saveInWorkspace: string = 'Yes (save in workspace settings)';

			let selection = await window.showWarningMessage(executableAndMessage.message, ...[saveInUser, saveInWorkspace, 'No']);
			// Try to use the Robocorp Code extension to provide one for us (if it's installed and
			// available).


			// robot.language-server.python
			if (selection == saveInUser || selection == saveInWorkspace) {
				let onfulfilled = await window.showOpenDialog({
					'canSelectMany': false,
					'openLabel': 'Select python exe'
				});
				if (!onfulfilled && onfulfilled.length > 0) {
					let configurationTarget: ConfigurationTarget = ConfigurationTarget.Workspace;
					if (selection == saveInUser) {
						configurationTarget = ConfigurationTarget.Global;
					}
					let config = workspace.getConfiguration("robot");
					config.update("language-server.python", onfulfilled[0].fsPath, configurationTarget);
					executableAndMessage = { 'executable': onfulfilled[0].fsPath, message: undefined };
				}
			} else {
				// There's not much we can do (besides start listening to changes to the related variables
				// on the finally block so that we start listening and ask for a reload if a related configuration changes).
				OUTPUT_CHANNEL.appendLine("Unable to start (no python executable specified).");
				return;
			}
		}

		let config = workspace.getConfiguration("robot");
		let port: number = config.get<number>("language-server.tcp-port");
		let langServer: LanguageClient;

		let initializationOptions: object = {};
		try {
			let pluginsDir: string = await commands.executeCommand<string>("robocorp.getPluginsDir");
			try {
				if (pluginsDir && pluginsDir.length > 0) {
					OUTPUT_CHANNEL.appendLine("Plugins dir: " + pluginsDir + ".");
					initializationOptions['pluginsDir'] = pluginsDir;
				}
			} catch (error) {
				OUTPUT_CHANNEL.appendLine(error);
			}
		} catch (error) {
			// The command may not be available.
		}

		if (port) {
			// For TCP server needs to be started seperately
			OUTPUT_CHANNEL.appendLine("Connecting to port: " + port);
			langServer = startLangServerTCP(port, initializationOptions);

		} else {
			let targetMain: string = path.resolve(__dirname, '../../src/robotframework_ls/__main__.py');
			if (!fs.existsSync(targetMain)) {
				window.showWarningMessage('Error. Expected: ' + targetMain + " to exist.");
				return;
			}

			let args: Array<string> = ["-u", targetMain];
			let config = workspace.getConfiguration("robot");
			let lsArgs = config.get<Array<string>>("language-server.args");
			if (lsArgs) {
				args = args.concat(lsArgs);
			}
			OUTPUT_CHANNEL.appendLine("Starting RobotFramework Language Server with args: " + executableAndMessage.executable + "," + args);
			langServer = startLangServerIO(executableAndMessage.executable, args, initializationOptions);
		}
		let disposable: Disposable = langServer.start();
		registerDebugger(executableAndMessage.executable);
		context.subscriptions.push(disposable);

		// i.e.: if we return before it's ready, the language server commands
		// may not be available.
		OUTPUT_CHANNEL.appendLine("Waiting for RobotFramework (python) Language Server to finish activating...");
		await langServer.onReady();

		langServer.onNotification("$/customProgress", (args: ProgressReport) => {
			// OUTPUT_CHANNEL.appendLine(args.id + ' - ' + args.kind + ' - ' + args.title + ' - ' + args.message + ' - ' + args.increment);
			handleProgressMessage(args)
		});

		OUTPUT_CHANNEL.appendLine("RobotFramework Language Server ready. Took: " + timing.getTotalElapsedAsStr());

		// registering Commands
		vscode.commands.registerCommand("robot.runTestcase", runTestcase)
		vscode.commands.registerCommand("robot.debugTestcase", debugTestcase)
		vscode.commands.registerCommand("robot.runTestsuite", runTestsuite)
		vscode.commands.registerCommand("robot.debugTestsuite", debugTestsuite)

	} finally {
		workspace.onDidChangeConfiguration(event => {
			for (let s of ["robot.language-server.python", "robot.language-server.tcp-port", "robot.language-server.args"]) {
				if (event.affectsConfiguration(s)) {
					window.showWarningMessage('Please use the "Reload Window" action for changes in ' + s + ' to take effect.', ...["Reload Window"]).then((selection) => {
						if (selection === "Reload Window") {
							commands.executeCommand("workbench.action.reloadWindow");
						}
					});
					return;
				}
			}
		});
	}
}


