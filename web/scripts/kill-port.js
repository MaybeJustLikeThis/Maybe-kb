import { spawnSync } from 'node:child_process'

const PORT = 3030

function run(command, args) {
  return spawnSync(command, args, { encoding: 'utf8' })
}

function killWindowsPort(port) {
  const find = run('powershell.exe', [
    '-NoProfile',
    '-Command',
    `$ErrorActionPreference = 'SilentlyContinue'; Get-NetTCPConnection -LocalPort ${port} | Select-Object -ExpandProperty OwningProcess -Unique`,
  ])
  if (find.status !== 0 && find.stdout.trim() === '') return true
  if (find.status !== 0) return false

  const ids = find.stdout.split(/\s+/).filter(Boolean)
  if (ids.length === 0) return true

  for (const id of ids) {
    const info = run('powershell.exe', [
      '-NoProfile',
      '-Command',
      `Get-Process -Id ${id} | Select-Object -ExpandProperty ProcessName`,
    ])
    const name = info.stdout.trim() || 'unknown'
    console.log(`Port ${port} is in use by PID ${id} (${name}). Killing...`)

    const gentle = run('powershell.exe', ['-NoProfile', '-Command', `Stop-Process -Id ${id} -ErrorAction SilentlyContinue`])
    if (gentle.status !== 0) {
      const force = run('powershell.exe', ['-NoProfile', '-Command', `Stop-Process -Id ${id} -Force -ErrorAction SilentlyContinue`])
      if (force.status !== 0) return false
    }
  }
  return true
}

function killUnixPort(port) {
  const find = run('sh', ['-c', `lsof -ti tcp:${port} 2>/dev/null`])
  if (find.status !== 0 && find.stdout.trim() === '') return true
  if (find.status !== 0) return false

  const ids = find.stdout.split(/\s+/).filter(Boolean)
  if (ids.length === 0) return true

  for (const id of ids) {
    const info = run('sh', ['-c', `ps -p ${id} -o comm= 2>/dev/null`])
    const name = info.stdout.trim() || 'unknown'
    console.log(`Port ${port} is in use by PID ${id} (${name}). Killing...`)

    const gentle = run('kill', [id])
    if (gentle.status !== 0) {
      const force = run('kill', ['-9', id])
      if (force.status !== 0) return false
    }
  }
  return true
}

const ok = process.platform === 'win32'
  ? killWindowsPort(PORT)
  : killUnixPort(PORT)

if (!ok) {
  console.error(`Failed to free port ${PORT}`)
  process.exit(1)
}
