import { useGetDashboardSummary, getGetDashboardSummaryQueryKey } from "@workspace/api-client-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { PageLoading, ErrorState, EmptyState } from "@/components/shared"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Link } from "wouter"
import { Clapperboard, Mic, FileText, Library, ActivitySquare, Plus, ArrowRight } from "lucide-react"
import { formatDate } from "@/lib/utils"

export default function DashboardPage() {
  const { data: summary, isLoading, error, refetch } = useGetDashboardSummary({
    query: { queryKey: getGetDashboardSummaryQueryKey(), refetchInterval: 10000 }
  })

  if (isLoading) return <PageLoading />
  if (error) return <ErrorState error={error} retry={() => refetch()} />
  if (!summary) return null

  const stats = [
    { label: "Projects", value: summary.projects, icon: Clapperboard, href: "/projects" },
    { label: "Voices", value: summary.voices, icon: Mic, href: "/voices" },
    { label: "Scripts", value: summary.scripts, icon: FileText, href: "/scripts" },
    { label: "Assets", value: summary.assets, icon: Library, href: "/library" },
  ]

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground mt-1 text-lg">Your production pipeline at a glance.</p>
        </div>
        <Link href="/projects">
          <Button className="shadow-md">
            <Plus className="w-4 h-4 mr-2" />
            New Project
          </Button>
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, i) => (
          <Link key={stat.label} href={stat.href}>
            <Card className="hover-elevate cursor-pointer transition-colors hover:border-primary/50 group">
              <CardContent className="p-6 flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground mb-1">{stat.label}</p>
                  <p className="text-3xl font-bold text-foreground">{stat.value}</p>
                </div>
                <div className="w-12 h-12 rounded-xl bg-secondary flex items-center justify-center text-secondary-foreground group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                  <stat.icon className="w-6 h-6" />
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold tracking-tight">Recent Jobs</h2>
            <Link href="/jobs">
              <Button variant="ghost" size="sm" className="text-muted-foreground">
                View all <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            </Link>
          </div>
          
          <Card>
            {summary.recentJobs.length === 0 ? (
              <EmptyState 
                title="No recent jobs" 
                description="Your rendering and processing jobs will appear here."
              />
            ) : (
              <div className="divide-y">
                {summary.recentJobs.map((job) => (
                  <div key={job.id} className="p-4 flex items-center justify-between hover:bg-muted/30 transition-colors">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-full bg-secondary flex items-center justify-center shrink-0">
                        <ActivitySquare className="w-5 h-5 text-muted-foreground" />
                      </div>
                      <div>
                        <p className="font-medium text-sm capitalize">{job.type.replace(/_/g, ' ')}</p>
                        <p className="text-xs text-muted-foreground">{formatDate(job.createdAt)}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      {job.status === 'running' && (
                        <div className="flex items-center gap-2 text-sm text-primary font-medium">
                          <span className="relative flex h-3 w-3">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-3 w-3 bg-primary"></span>
                          </span>
                          {job.progress}%
                        </div>
                      )}
                      <Badge variant={
                        job.status === 'done' ? 'success' :
                        job.status === 'failed' ? 'destructive' :
                        job.status === 'running' ? 'default' : 'secondary'
                      }>
                        {job.status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-4">
          <h2 className="text-xl font-semibold tracking-tight">Quick Actions</h2>
          <Card>
            <div className="divide-y flex flex-col">
              <Link href="/voices" className="p-4 flex items-center justify-between hover:bg-muted/30 group transition-colors">
                <div className="flex items-center gap-3">
                  <Mic className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
                  <span className="font-medium text-sm">Clone a Voice</span>
                </div>
                <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
              </Link>
              <Link href="/scripts" className="p-4 flex items-center justify-between hover:bg-muted/30 group transition-colors">
                <div className="flex items-center gap-3">
                  <FileText className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
                  <span className="font-medium text-sm">Write a Script</span>
                </div>
                <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
              </Link>
              <Link href="/library" className="p-4 flex items-center justify-between hover:bg-muted/30 group transition-colors">
                <div className="flex items-center gap-3">
                  <Library className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
                  <span className="font-medium text-sm">Upload Assets</span>
                </div>
                <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
              </Link>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
