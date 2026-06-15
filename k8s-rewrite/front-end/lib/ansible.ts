import { spawn } from 'child_process';
import fs from 'fs/promises';
import path from 'path';

const PLAYBOOK_PATH = process.env.ANSIBLE_PLAYBOOK_PATH || './k8s-rewrite/ansible-playbook/playbooks/site.yml';
const INVENTORY_PATH = process.env.ANSIBLE_INVENTORY_PATH || './k8s-rewrite/ansible-playbook/inventory/production.ini';
const VARS_PATH = process.env.ANSIBLE_VARS_PATH || './k8s-rewrite/ansible-playbook/group_vars/all.yml';

export interface AnsibleOutputLine {
  timestamp: Date;
  level: 'info' | 'success' | 'warning' | 'error';
  message: string;
}

export interface JobResult {
  jobId: string;
  status: 'running' | 'success' | 'failed';
  output: AnsibleOutputLine[];
  exitCode?: number;
}

export class AnsibleRunner {
  async run(playbook: string, roles?: string[]): Promise<JobResult> {
    const outputLines: AnsibleOutputLine[] = [];

    return new Promise((resolve, reject) => {
      const command = ['ansible-playbook', playbook];

      if (roles && roles.length > 0) {
        command.push('--tags', roles.join(','));
      }

      command.push('-i', INVENTORY_PATH);
      command.push('-vvv');

      const process = spawn('ansible-playbook', command, {
        cwd: path.dirname(PLAYBOOK_PATH),
        shell: false,
        stdio: ['pipe', 'pipe', 'pipe'],
      });

      process.stdout.on('data', (data: Buffer) => {
        const text = data.toString();
        const lines = text.split('\n').filter(line => line.trim());
        for (const line of lines) {
          const parsed = this.parseLine(line);
          if (parsed) {
            outputLines.push(parsed);
          }
        }
      });

      process.stderr.on('data', (data: Buffer) => {
        const text = data.toString();
        const lines = text.split('\n').filter(line => line.trim());
        for (const line of lines) {
          const parsed = this.parseLine(line);
          if (parsed && parsed.level === 'error') {
            outputLines.push(parsed);
          }
        }
      });

      process.on('close', (code: number) => {
        resolve({
          jobId: crypto.randomUUID(),
          status: code === 0 ? 'success' : 'failed',
          output: outputLines,
          exitCode: code,
        });
      });

      process.on('error', (err: Error) => {
        reject(err);
      });
    });
  }

  private parseLine(line: string): AnsibleOutputLine | null {
    const trimmed = line.trim();

    if (!trimmed || trimmed.startsWith('PLAY [') || trimmed.includes('TASK [') || trimmed.includes('RUNNING')) {
      return null;
    }

    if (trimmed.match(/changed=0|ok=\d+/)) {
      return {
        timestamp: new Date(),
        level: 'success',
        message: trimmed,
      };
    }

    if (trimmed.includes('WARNING') || trimmed.includes('WARNINGS')) {
      return {
        timestamp: new Date(),
        level: 'warning',
        message: trimmed,
      };
    }

    if (trimmed.match(/ERROR|FATAL|failed/)) {
      return {
        timestamp: new Date(),
        level: 'error',
        message: trimmed,
      };
    }

    return {
      timestamp: new Date(),
      level: 'info',
      message: trimmed,
    };
  }
}

// Generate YAML from variables object
export async function generateYamlFromVars(vars: Record<string, string>): Promise<string> {
  const lines: string[] = [];
  let currentSection = '';

  for (const [key, value] of Object.entries(vars)) {
    if (key.startsWith('#')) {
      currentSection = key.replace('#', '').trim();
      lines.push(`# ${currentSection}`);
      continue;
    }

    if (!key || key === '') continue;

    const formattedKey = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    lines.push(`${formattedKey}: ${value}`);
  }

  return lines.join('\n');
}

// Write variables to Ansible group_vars file
export async function writeVarsToFile(vars: Record<string, string>, filePath: string): Promise<void> {
  const yamlContent = await generateYamlFromVars(vars);
  await fs.writeFile(filePath, yamlContent, 'utf8');
}

// Read existing variables from Ansible group_vars file
export async function readVarsFromFile(filePath: string): Promise<Record<string, string>> {
  try {
    const content = await fs.readFile(filePath, 'utf8');
    const vars: Record<string, string> = {};

    for (const line of content.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) continue;

      const [key, ...valueParts] = trimmed.split(':');
      const keyName = key.trim().replace(/"/g, '').replace(/'/g, '');
      const value = valueParts.join(':').trim().replace(/"/g, '').replace(/'/g, '');

      if (keyName && value) {
        vars[keyName] = value;
      }
    }

    return vars;
  } catch (error) {
    console.error('Error reading vars file:', error);
    return {};
  }
}

// Generate inventory content from inventory object
export async function generateInventory(inventory: Record<string, string>): Promise<string> {
  const lines: string[] = [];

  lines.push('# Kubernetes Cluster Inventory');
  lines.push('# Edit this file with your actual node IP addresses and hostnames');
  lines.push('');
  lines.push('[all]');

  for (const [hostname, data] of Object.entries(inventory)) {
    // Simple string-based inventory format
    const ansibleHost = data;
    const ansibleUser = 'root';
    const ansiblePythonInterpreter = '/usr/bin/python3';

    lines.push(`${hostname} ansible_host=${ansibleHost} ansible_user=${ansibleUser} ansible_python_interpreter=${ansiblePythonInterpreter}`);
  }

  lines.push('');
  lines.push('[groups]');
  const master = inventory['master'] || '';
  const workers = Object.keys(inventory).filter(h => h !== 'master').join(', ') || '';
  lines.push(`master = ${master}`);
  lines.push(`workers = ${workers}`);
  lines.push(`k8s_nodes = master,${workers}`);

  lines.push('');
  lines.push('[vars]');
  lines.push('ansible_connection=ssh');
  lines.push("ansible_ssh_common_args='-o StrictHostKeyChecking=no'");

  return lines.join('\n');
}

// Write inventory to file
export async function writeInventoryToFile(inventory: Record<string, string>, filePath: string): Promise<void> {
  const content = await generateInventory(inventory);
  await fs.writeFile(filePath, content, 'utf8');
}