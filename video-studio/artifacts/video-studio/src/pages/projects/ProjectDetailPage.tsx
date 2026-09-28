import { useState } from "react"
import { useParams } from "wouter"
import { 
  useGetProject, 
  useUpdateProject, 
  useListJobs, 
  useRunProjectPipeline,
  useListAssets,
  useListScripts,
  useListVoices,
  useGetAsset,
  useCancelJob,
  useRetryJob,
  getGetProjectQueryKey,
  getListJobsQueryKey
} from "@workspace/api-client-react"
import { useQueryClient } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { PageLoading, ErrorState } from "@/components/shared"
import { formatDate } from "@/lib/utils"
import { Play, Film, Mic, FileText, ActivitySquare, Settings2, XCircle, RotateCcw, AlertTriangle, Send } from "lucide-react"

function AssetPreview({ assetId, type = "video" }: { assetId: string, type?: "video" | "audio" }) {
  const { data: asset, isLoading } = useGetAsset(assetId, {
    query: { queryKey: ['asset', assetId], enabled: !!assetId }
  })
  
  if (isLoading) return <div className="aspect-video bg-muted animate-pulse rounded-md" />
  if (!asset) return <div className="aspect-video bg-muted rounded-md flex items-center justify-center text-muted-foreground text-sm">Asset not found</div>
  
  return (
    <div className="rounded-md overflow-hidden bg-black aspect-video relative group flex items-center justify-center">
      {type === 'video' ? (
        <video 
          src={`/api/storage${asset.objectPath}`} 
          className="w-full h-full object-contain"
          controls
        />
      ) : (
        <audio 
          src={`/api/storage${asset.objectPath}`} 
          className="w-full mx-4"
          controls
        />
      )}
    </div>
  )
}

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()

  const { data: project, isLoading: projectLoading, error: projectError, refetch: refetchProject } = useGetProject(id, {
    query: { queryKey: getGetProjectQueryKey(id), enabled: !!id, refetchInterval: 10000 }
  })

  const { data: jobs, isLoading: jobsLoading } = useListJobs(
    { projectId: id },
    { query: { queryKey: getListJobsQueryKey({ projectId: id }), enabled: !!id, refetchInterval: 5000 } }
  )

  const { data: sourceVideos } = useListAssets({ kind: "source_video" })
  const { data: scripts } = useListScripts()
  const { data: voices } = useListVoices()

  const updateProject = useUpdateProject({ mutation: { onSuccess: () => queryClient.invalidateQueries({ queryKey: getGetProjectQueryKey(id) }) } })
  const runPipeline = useRunProjectPipeline({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetProjectQueryKey(id) })
        queryClient.invalidateQueries({ queryKey: getListJobsQueryKey({ projectId: id }) })
      }
    }
  })
  const cancelJob = useCancelJob({ mutation: { onSuccess: () => queryClient.invalidateQueries({ queryKey: getListJobsQueryKey({ projectId: id }) }) } })
  const retryJob = useRetryJob({ mutation: { onSuccess: () => queryClient.invalidateQueries({ queryKey: getListJobsQueryKey({ projectId: id }) }) } })

  const [brollCount, setBrollCount] = useState<number>(0)
  const [deliver, setDeliver] = useState<boolean>(false)

  if (projectLoading || jobsLoading) return <PageLoading />
  if (projectError) return <ErrorState error={projectError} retry={() => refetchProject()} />
  if (!project) return null

  const isConfigComplete = project.sourceAssetId && project.scriptId && project.voiceId
  const isRunning = project.status === 'processing' || jobs?.some(j => j.status === 'running' || j.status === 'queued')

  const handleUpdate = (field: string, value: string) => {
    updateProject.mutate({ projectId: id, data: { [field]: value } })
  }

  const handleRunPipeline = () => {
    runPipeline.mutate({
      projectId: id,
      data: {
        brollCount,
        deliver
      }
    })
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-3xl font-bold tracking-tight">{project.title}</h1>
            <Badge variant={
              project.status === 'delivered' ? 'success' :
              project.status === 'failed' ? 'destructive' :
              project.status === 'processing' ? 'default' :
              project.status === 'ready' ? 'secondary' : 'outline'
            } className="uppercase text-[10px] px-2 py-0.5">
              {project.status}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">Last updated {formatDate(project.updatedAt)}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column - Configuration & Outputs */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader className="pb-4">
              <CardTitle>Configuration</CardTitle>
              <CardDescription>Select the raw materials for this render.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div className="space-y-2">
                  <Label className="flex items-center gap-2"><Film className="w-4 h-4 text-muted-foreground" /> Source Video</Label>
                  <Select 
                    value={project.sourceAssetId || ""} 
                    onValueChange={(val) => handleUpdate("sourceAssetId", val)}
                    disabled={isRunning}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select a video..." />
                    </SelectTrigger>
                    <SelectContent>
                      {sourceVideos?.map(v => (
                        <SelectItem key={v.id} value={v.id}>{v.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label className="flex items-center gap-2"><FileText className="w-4 h-4 text-muted-foreground" /> Script</Label>
                  <Select 
                    value={project.scriptId || ""} 
                    onValueChange={(val) => handleUpdate("scriptId", val)}
                    disabled={isRunning}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select a script..." />
                    </SelectTrigger>
                    <SelectContent>
                      {scripts?.map(s => (
                        <SelectItem key={s.id} value={s.id}>{s.title}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label className="flex items-center gap-2"><Mic className="w-4 h-4 text-muted-foreground" /> Voice Clone</Label>
                  <Select 
                    value={project.voiceId || ""} 
                    onValueChange={(val) => handleUpdate("voiceId", val)}
                    disabled={isRunning}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select a voice..." />
                    </SelectTrigger>
                    <SelectContent>
                      {voices?.filter(v => v.status === 'ready').map(v => (
                        <SelectItem key={v.id} value={v.id}>{v.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Outputs */}
          {(project.renderAssetId || project.voiceoverAssetId) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {project.renderAssetId && (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <Play className="w-4 h-4 text-primary" /> Final Render
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <AssetPreview assetId={project.renderAssetId} type="video" />
                  </CardContent>
                </Card>
              )}
              {project.voiceoverAssetId && (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <Mic className="w-4 h-4 text-primary" /> Generated Voiceover
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <AssetPreview assetId={project.voiceoverAssetId} type="audio" />
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </div>

        {/* Right Column - Pipeline & Jobs */}
        <div className="space-y-6">
          <Card className="border-primary/20 shadow-md">
            <CardHeader className="pb-4">
              <CardTitle className="flex items-center gap-2">
                <Settings2 className="w-5 h-5 text-primary" /> Pipeline
              </CardTitle>
              <CardDescription>Configure and run the processing pipeline.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4 bg-muted/30 p-4 rounded-lg border border-border">
                <div className="space-y-2">
                  <Label>AI B-Roll Count</Label>
                  <Select 
                    value={brollCount.toString()} 
                    onValueChange={(val) => setBrollCount(parseInt(val))}
                    disabled={isRunning}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="0">None</SelectItem>
                      <SelectItem value="1">1 clip</SelectItem>
                      <SelectItem value="2">2 clips</SelectItem>
                      <SelectItem value="3">3 clips</SelectItem>
                      <SelectItem value="4">4 clips</SelectItem>
                      <SelectItem value="5">5 clips</SelectItem>
                      <SelectItem value="6">6 clips</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="flex items-center space-x-2">
                  <Checkbox 
                    id="deliver" 
                    checked={deliver} 
                    onCheckedChange={(c) => setDeliver(!!c)} 
                    disabled={isRunning}
                  />
                  <Label htmlFor="deliver" className="cursor-pointer font-normal text-muted-foreground flex items-center gap-2">
                    <Send className="w-4 h-4" /> Automatically deliver via FTP
                  </Label>
                </div>
              </div>

              <Button 
                className="w-full h-12 text-base" 
                size="lg"
                disabled={!isConfigComplete || isRunning || runPipeline.isPending}
                onClick={handleRunPipeline}
              >
                {isRunning ? (
                  <>Pipeline Running...</>
                ) : runPipeline.isPending ? (
                  <>Queuing Jobs...</>
                ) : !isConfigComplete ? (
                  <>Complete Config to Run</>
                ) : (
                  <>Run Pipeline</>
                )}
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-4">
              <CardTitle className="text-base flex items-center gap-2">
                <ActivitySquare className="w-4 h-4" /> Active Jobs
              </CardTitle>
            </CardHeader>
            <CardContent className="px-0 pb-0">
              {(!jobs || jobs.length === 0) ? (
                <div className="p-6 text-center text-sm text-muted-foreground border-t border-border border-dashed mx-6 mb-6 rounded-b-lg">
                  No jobs have run for this project.
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {jobs.map((job) => (
                    <div key={job.id} className="p-4 hover:bg-muted/20 transition-colors group">
                      <div className="flex items-center justify-between mb-2">
                        <div className="font-medium text-sm capitalize">{job.type.replace(/_/g, ' ')}</div>
                        <Badge variant={
                          job.status === 'done' ? 'success' :
                          job.status === 'failed' ? 'destructive' :
                          job.status === 'running' ? 'default' :
                          job.status === 'canceled' ? 'outline' : 'secondary'
                        } className="text-[10px]">
                          {job.status}
                        </Badge>
                      </div>
                      
                      {job.status === 'running' && (
                        <div className="space-y-1 mb-2">
                          <div className="flex justify-between text-xs text-muted-foreground">
                            <span>{job.message || 'Processing...'}</span>
                            <span>{job.progress}%</span>
                          </div>
                          <div className="h-1.5 w-full bg-secondary rounded-full overflow-hidden">
                            <div className="h-full bg-primary transition-all duration-500 ease-in-out" style={{ width: `${job.progress}%` }} />
                          </div>
                        </div>
                      )}
                      
                      {job.error && (
                        <div className="flex items-start gap-2 text-xs text-destructive bg-destructive/10 p-2 rounded mt-2">
                          <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                          <span>{job.error}</span>
                        </div>
                      )}

                      <div className="flex items-center justify-between mt-2 text-xs text-muted-foreground">
                        <span>{formatDate(job.startedAt || job.createdAt)}</span>
                        <div className="opacity-0 group-hover:opacity-100 transition-opacity flex gap-2">
                          {(job.status === 'queued' || job.status === 'running') && (
                            <button 
                              className="text-muted-foreground hover:text-destructive flex items-center"
                              onClick={() => cancelJob.mutate({ jobId: job.id })}
                            >
                              <XCircle className="w-3 h-3 mr-1" /> Cancel
                            </button>
                          )}
                          {(job.status === 'failed' || job.status === 'canceled') && (
                            <button 
                              className="text-muted-foreground hover:text-foreground flex items-center"
                              onClick={() => retryJob.mutate({ jobId: job.id })}
                            >
                              <RotateCcw className="w-3 h-3 mr-1" /> Retry
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
