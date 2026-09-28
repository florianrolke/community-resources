import { useGetSettingsStatus } from "@workspace/api-client-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { PageLoading, ErrorState } from "@/components/shared"
import { Badge } from "@/components/ui/badge"
import { CheckCircle2, XCircle, HardDrive, Cpu, Cloud, Settings2 } from "lucide-react"

export default function SettingsPage() {
  const { data: status, isLoading, error, refetch } = useGetSettingsStatus()

  if (isLoading) return <PageLoading />
  if (error) return <ErrorState error={error} retry={() => refetch()} />
  if (!status) return null

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">System Status</h1>
        <p className="text-muted-foreground mt-1">Read-only health check of external providers and connections.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* Voice Provider */}
        <Card className="hover-elevate transition-colors border-border shadow-sm">
          <CardHeader className="pb-4">
            <div className="flex items-start justify-between">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary mb-3">
                <Cpu className="w-5 h-5" />
              </div>
              {status.voice.configured ? (
                <Badge variant="success" className="gap-1"><CheckCircle2 className="w-3 h-3" /> Online</Badge>
              ) : (
                <Badge variant="destructive" className="gap-1"><XCircle className="w-3 h-3" /> Offline</Badge>
              )}
            </div>
            <CardTitle>Voice Cloning</CardTitle>
            <CardDescription>AI voice synthesis provider</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between py-2 border-b border-border">
                <span className="text-muted-foreground">Provider</span>
                <span className="font-medium">{status.voice.detail || "Not Configured"}</span>
              </div>
              {status.voice.credit !== undefined && status.voice.credit !== null && (
                <div className="flex justify-between py-2 border-b border-border">
                  <span className="text-muted-foreground">Credit</span>
                  <span className="font-medium">${status.voice.credit.toFixed(2)}</span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* B-Roll Provider */}
        <Card className="hover-elevate transition-colors border-border shadow-sm">
          <CardHeader className="pb-4">
            <div className="flex items-start justify-between">
              <div className="w-10 h-10 rounded-lg bg-orange-500/10 flex items-center justify-center text-orange-500 mb-3">
                <Cloud className="w-5 h-5" />
              </div>
              {status.broll.configured ? (
                <Badge variant="success" className="gap-1"><CheckCircle2 className="w-3 h-3" /> Online</Badge>
              ) : (
                <Badge variant="destructive" className="gap-1"><XCircle className="w-3 h-3" /> Offline</Badge>
              )}
            </div>
            <CardTitle>AI B-Roll</CardTitle>
            <CardDescription>Generative video for cutaways</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between py-2 border-b border-border">
                <span className="text-muted-foreground">Provider</span>
                <span className="font-medium">{status.broll.detail || "Not Configured"}</span>
              </div>
              {status.broll.credit !== undefined && status.broll.credit !== null && (
                <div className="flex justify-between py-2 border-b border-border">
                  <span className="text-muted-foreground">Credit</span>
                  <span className="font-medium">${status.broll.credit.toFixed(2)}</span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* FTP Provider */}
        <Card className="hover-elevate transition-colors border-border shadow-sm">
          <CardHeader className="pb-4">
            <div className="flex items-start justify-between">
              <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center text-blue-500 mb-3">
                <HardDrive className="w-5 h-5" />
              </div>
              {status.ftp.configured ? (
                <Badge variant="success" className="gap-1"><CheckCircle2 className="w-3 h-3" /> Connected</Badge>
              ) : (
                <Badge variant="secondary" className="gap-1"><Settings2 className="w-3 h-3" /> Unconfigured</Badge>
              )}
            </div>
            <CardTitle>FTP Delivery</CardTitle>
            <CardDescription>Automated output routing</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between py-2 border-b border-border">
                <span className="text-muted-foreground">Status</span>
                <span className="font-medium">{status.ftp.detail || "Configuration missing"}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="p-4 bg-muted/50 rounded-lg border border-dashed flex items-center gap-3 text-sm text-muted-foreground max-w-3xl">
        <Settings2 className="w-5 h-5 shrink-0" />
        <p>
          Configuration values are securely managed through environment variables on the backend. 
          Changes require a server restart to take effect.
        </p>
      </div>
    </div>
  )
}
