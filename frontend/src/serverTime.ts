// The server's timers run on its own clock. Every response carries its time, so a countdown on
// a phone with a slightly wrong clock still shows what the server will actually do.
let skewMs = 0

export function setServerTime(serverSeconds: number): void {
  skewMs = serverSeconds * 1000 - Date.now()
}

/** The server's time now, in seconds. */
export function serverNow(): number {
  return (Date.now() + skewMs) / 1000
}
