/** 页面级写锁不能从 sessionStorage 复制；服务端代次负责最终拒绝旧页面写入。 */
export function createPageLease(
  userId: string,
  attemptId: string,
  onRevoked: (suspended?: boolean) => void,
) {
  const name = `online-exam-attempt:${userId}:${attemptId}`
  const owner = crypto.randomUUID()
  const channel = new BroadcastChannel(name)
  let releaseLock: (() => void) | null = null
  let held = false
  let closed = false
  let claim = 0
  const release = (): void => {
    held = false
    releaseLock?.()
    releaseLock = null
  }
  channel.onmessage = (event: MessageEvent<{ type: string; owner: string }>) => {
    if (event.data.owner === owner || event.data.type !== 'takeover') return
    if (held) {
      onRevoked()
      release()
    }
  }
  async function acquire(takeover = false): Promise<boolean> {
    if (closed || !('locks' in navigator)) return false
    if (held) return true
    const currentClaim = ++claim
    if (takeover) channel.postMessage({ type: 'takeover', owner })
    return new Promise<boolean>((resolve) => {
      void navigator.locks
        .request(name, takeover ? { steal: true } : { ifAvailable: true }, async (lock) => {
          if (!lock || closed) {
            resolve(false)
            return
          }
          held = true
          resolve(true)
          await new Promise<void>((finish) => {
            releaseLock = finish
          })
        })
        .catch(() => {
          if (held && currentClaim === claim) {
            onRevoked()
            release()
          }
          resolve(false)
        })
    })
  }
  const pageHide = (): void => {
    onRevoked(true)
    release()
  }
  window.addEventListener('pagehide', pageHide)
  function close(): void {
    closed = true
    release()
    channel.close()
    window.removeEventListener('pagehide', pageHide)
  }
  return {
    acquire,
    release,
    close,
    broadcastTakeover: () => channel.postMessage({ type: 'takeover', owner }),
  }
}
