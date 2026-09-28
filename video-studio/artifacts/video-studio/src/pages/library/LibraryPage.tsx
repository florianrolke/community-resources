import { useState, useRef } from "react"
import { useListAssets, useCreateAsset, useDeleteAsset, getListAssetsQueryKey, useRequestUploadUrl } from "@workspace/api-client-react"
import { useQueryClient } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { PageLoading, ErrorState, EmptyState } from "@/components/shared"
import { formatDate, formatBytes } from "@/lib/utils"
import { Trash2, Film, Music, FileAudio, Video, File, Plus } from "lucide-react"
import { ObjectUploader } from "@workspace/object-storage-web"

export default function LibraryPage() {
  const [filterKind, setFilterKind] = useState<string>("all")
  const queryClient = useQueryClient()
  
  const { data: assets, isLoading, error, refetch } = useListAssets(
    filterKind !== "all" ? { kind: filterKind as any } : undefined,
    { query: { queryKey: getListAssetsQueryKey(filterKind !== "all" ? { kind: filterKind as any } : undefined) } }
  )

  const requestUploadUrl = useRequestUploadUrl()
  const createAsset = useCreateAsset({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListAssetsQueryKey() })
      }
    }
  })
  const deleteAsset = useDeleteAsset({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListAssetsQueryKey() })
      }
    }
  })

  // To map Uppy file IDs to our requested object paths
  const uploadPaths = useRef<Record<string, string>>({})
  const [uploadKind, setUploadKind] = useState<"source_video" | "voice_sample">("source_video")
  const [isUploaderOpen, setIsUploaderOpen] = useState(false)

  if (isLoading) return <PageLoading />
  if (error) return <ErrorState error={error} retry={() => refetch()} />

  const getIcon = (kind: string) => {
    switch (kind) {
      case "source_video": return <Film className="w-8 h-8 text-blue-500" />
      case "voice_sample": return <Music className="w-8 h-8 text-purple-500" />
      case "audio": return <FileAudio className="w-8 h-8 text-yellow-500" />
      case "voiceover": return <Mic className="w-8 h-8 text-green-500" />
      case "broll": return <Video className="w-8 h-8 text-orange-500" />
      case "render": return <Film className="w-8 h-8 text-primary" />
      default: return <File className="w-8 h-8 text-muted-foreground" />
    }
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Library</h1>
          <p className="text-muted-foreground mt-1">All your source files, intermediate assets, and final renders.</p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={filterKind} onValueChange={setFilterKind}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Filter by kind" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Assets</SelectItem>
              <SelectItem value="source_video">Source Videos</SelectItem>
              <SelectItem value="voice_sample">Voice Samples</SelectItem>
              <SelectItem value="audio">Audio Extractions</SelectItem>
              <SelectItem value="voiceover">Voiceovers</SelectItem>
              <SelectItem value="broll">B-Roll</SelectItem>
              <SelectItem value="render">Renders</SelectItem>
            </SelectContent>
          </Select>

          {!isUploaderOpen ? (
            <Button onClick={() => setIsUploaderOpen(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Upload Media
            </Button>
          ) : (
            <Button variant="outline" onClick={() => setIsUploaderOpen(false)}>Cancel Upload</Button>
          )}
        </div>
      </div>

      {isUploaderOpen && (
        <Card className="border-primary/30 shadow-md">
          <CardHeader>
            <CardTitle>Upload Media</CardTitle>
            <CardDescription>Choose the type of media you are uploading, then select files.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="w-full max-w-xs">
              <label className="text-sm font-medium mb-2 block">Asset Type</label>
              <Select value={uploadKind} onValueChange={(val: any) => setUploadKind(val)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="source_video">Source Video (for cutting)</SelectItem>
                  <SelectItem value="voice_sample">Voice Sample (for cloning)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <ObjectUploader
              onGetUploadParameters={async (file) => {
                const res = await requestUploadUrl.mutateAsync({
                  data: { name: file.name, size: file.size ?? 0, contentType: file.type || "application/octet-stream" }
                })
                uploadPaths.current[file.id] = res.objectPath
                return {
                  method: "PUT",
                  url: res.uploadURL,
                  headers: { "Content-Type": file.type || "application/octet-stream" }
                }
              }}
              onComplete={(result) => {
                (result.successful ?? []).forEach(f => {
                  const objectPath = uploadPaths.current[f.id]
                  if (objectPath) {
                    createAsset.mutate({
                      data: {
                        name: f.name,
                        kind: uploadKind,
                        objectPath,
                        contentType: f.type,
                        size: f.size ?? undefined
                      }
                    })
                  }
                })
                setIsUploaderOpen(false)
              }}
            >
              Select files to upload
            </ObjectUploader>
          </CardContent>
        </Card>
      )}

      {(!assets || assets.length === 0) ? (
        <EmptyState 
          title="No assets found" 
          description="Upload some media to get started, or clear your filters."
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {assets.map((asset) => (
            <Card key={asset.id} className="overflow-hidden group">
              <div className="aspect-video bg-muted flex flex-col items-center justify-center relative border-b border-border">
                {getIcon(asset.kind)}
                
                {/* Media Preview if applicable */}
                {(asset.contentType?.startsWith('video/') || asset.kind === 'render' || asset.kind === 'source_video' || asset.kind === 'broll') && (
                  <video 
                    src={`/api/storage${asset.objectPath}`} 
                    className="absolute inset-0 w-full h-full object-cover opacity-0 group-hover:opacity-100 transition-opacity"
                    muted loop playsInline
                    onMouseOver={e => (e.target as HTMLVideoElement).play().catch(()=>{})}
                    onMouseOut={e => {
                      const v = e.target as HTMLVideoElement;
                      v.pause();
                      v.currentTime = 0;
                    }}
                  />
                )}
                
                {(asset.contentType?.startsWith('audio/') || asset.kind === 'voice_sample' || asset.kind === 'audio' || asset.kind === 'voiceover') && (
                  <audio 
                    src={`/api/storage${asset.objectPath}`} 
                    className="absolute bottom-2 left-2 right-2 w-[calc(100%-16px)] h-8 opacity-0 group-hover:opacity-100 transition-opacity"
                    controls
                  />
                )}
              </div>
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-semibold text-sm truncate" title={asset.name}>{asset.name}</p>
                    <p className="text-xs text-muted-foreground mt-1 flex items-center gap-2">
                      <span>{formatBytes(asset.size)}</span>
                      <span>•</span>
                      <span>{formatDate(asset.createdAt)}</span>
                    </p>
                  </div>
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className="h-8 w-8 text-muted-foreground hover:text-destructive shrink-0"
                    onClick={() => {
                      if (confirm(`Delete asset ${asset.name}?`)) {
                        deleteAsset.mutate({ assetId: asset.id })
                      }
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
                <div className="mt-3">
                  <Badge variant="secondary" className="text-[10px] capitalize">
                    {asset.kind.replace(/_/g, ' ')}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

function Mic({ className }: { className?: string }) {
  return <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>
}
