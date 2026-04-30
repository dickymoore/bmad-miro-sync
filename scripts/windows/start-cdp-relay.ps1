$ErrorActionPreference = "Stop"

param(
  [int]$ListenPort = 9223,
  [string]$TargetHost = "127.0.0.1",
  [int]$TargetPort = 9222
)

Add-Type -AssemblyName System.Net
Add-Type -AssemblyName System.Net.Sockets

$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse("0.0.0.0"), $ListenPort)
$listener.Server.SetSocketOption([System.Net.Sockets.SocketOptionLevel]::Socket, [System.Net.Sockets.SocketOptionName]::ReuseAddress, $true)
$listener.Start()

Write-Host "CDP relay listening on 0.0.0.0:$ListenPort and forwarding to $TargetHost:$TargetPort"
Write-Host "Leave this PowerShell window open while Codex is running."

function Start-RelayCopy {
  param(
    [System.IO.Stream]$Source,
    [System.IO.Stream]$Destination
  )

  return [System.Threading.Tasks.Task]::Run({
    param($src, $dst)
    $buffer = New-Object byte[] 8192
    try {
      while ($true) {
        $read = $src.Read($buffer, 0, $buffer.Length)
        if ($read -le 0) { break }
        $dst.Write($buffer, 0, $read)
        $dst.Flush()
      }
    } catch {
    } finally {
      try { $dst.Close() } catch {}
      try { $src.Close() } catch {}
    }
  }, @($Source, $Destination))
}

try {
  while ($true) {
    $client = $listener.AcceptTcpClient()
    [System.Threading.Tasks.Task]::Run({
      param($acceptedClient, $forwardHost, $forwardPort)
      $upstream = $null
      try {
        $upstream = [System.Net.Sockets.TcpClient]::new()
        $upstream.Connect($forwardHost, $forwardPort)

        $clientStream = $acceptedClient.GetStream()
        $upstreamStream = $upstream.GetStream()

        $t1 = Start-RelayCopy -Source $clientStream -Destination $upstreamStream
        $t2 = Start-RelayCopy -Source $upstreamStream -Destination $clientStream

        [System.Threading.Tasks.Task]::WaitAny(@($t1, $t2)) | Out-Null
      } catch {
        Write-Warning $_
      } finally {
        try { $acceptedClient.Close() } catch {}
        if ($upstream) {
          try { $upstream.Close() } catch {}
        }
      }
    }, @($client, $TargetHost, $TargetPort)) | Out-Null
  }
} finally {
  $listener.Stop()
}
