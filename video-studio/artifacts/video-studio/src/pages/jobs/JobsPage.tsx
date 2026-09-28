import { useListJobs, useCancelJob, useRetryJob, getListJobsQueryKey } from "@workspace/api-client-react"
import { useQueryClient } from "@tanstack/react-query"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { PageLoading, ErrorState, EmptyState } from "@/components/shared"
import { formatDate } from "@/lib/utils"
import { ActivitySquare, XCircle, RotateCcw, AlertTriangle } from "lucide-react"

export default function JobsPage() {
  const queryClient = useQueryClient()
  
  const { data: jobs, isLoading, error, refetch } = useListJobs(undefined, {
    query: { queryKey: getListJobsQueryKey(), refetchInterval: 5000 }
  })
  
  const cancelJob = useCancelJob({ mutation: { onSuccess: () => queryClient.invalidateQueries({ queryKey: getListJobsQueryKey() }) } })
  const retryJob = useRetryJob({ mutation: { onSuccess: () => queryClient.invalidateQueries({ queryKey: getListJobsQueryKey() }) } })

  if (isLoading) return <PageLoading />
  if (error) return <ErrorState error={error} retry={() => refetch()} />

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Job History</h1>
        <p className="text-muted-foreground mt-1">Monitor the cloud rendering and processing pipeline.</p>
      </div>

      <Card className="overflow-hidden shadow-sm border-border">
        {(!jobs || jobs.length === 0) ? (
          <EmptyState 
            title="No jobs yet" 
            description="Run a project pipeline or clone a voice to see activity here."
          />
        ) : (
          <Table>
            <TableHeader className="bg-muted/50">
              <TableRow>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Details</TableHead>
                <TableHead>Started</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.map((job) => (
                <TableRow key={job.id} className="group">
                  <TableCell className="font-medium capitalize">
                    <div className="flex items-center gap-2">
                      <ActivitySquare className="w-4 h-4 text-muted-foreground" />
                      {job.type.replace(/_/g, ' ')}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {job.status === 'running' && (
                        <span className="relative flex h-2 w-2">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                          <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                        </span>
                      )}
                      <Badge variant={
                        job.status === 'done' ? 'success' :
                        job.status === 'failed' ? 'destructive' :
                        job.status === 'running' ? 'default' :
                        job.status === 'canceled' ? 'outline' : 'secondary'
                      }>
                        {job.status}
                      </Badge>
                      {job.status === 'running' && (
                        <span className="text-xs font-medium text-muted-foreground">{job.progress}%</span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="max-w-[200px] lg:max-w-[300px]">
                      {job.message && (
                        <p className="text-xs text-muted-foreground truncate" title={job.message}>{job.message}</p>
                      )}
                      {job.error && (
                        <div className="flex items-start gap-1 text-destructive mt-1">
                          <AlertTriangle className="w-3 h-3 shrink-0 mt-0.5" />
                          <p className="text-xs truncate font-medium" title={job.error}>{job.error}</p>
                        </div>
                      )}
                      {!job.message && !job.error && (
                        <span className="text-xs text-muted-foreground/50">—</span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-xs whitespace-nowrap">
                    {formatDate(job.startedAt || job.createdAt)}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      {(job.status === 'queued' || job.status === 'running') && (
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          className="h-8 text-muted-foreground hover:text-destructive"
                          onClick={() => cancelJob.mutate({ jobId: job.id })}
                          disabled={cancelJob.isPending}
                        >
                          <XCircle className="w-4 h-4 mr-1" /> Cancel
                        </Button>
                      )}
                      {(job.status === 'failed' || job.status === 'canceled') && (
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          className="h-8 text-muted-foreground"
                          onClick={() => retryJob.mutate({ jobId: job.id })}
                          disabled={retryJob.isPending}
                        >
                          <RotateCcw className="w-4 h-4 mr-1" /> Retry
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  )
}
