import { useState } from "react"
import { useListVoices, useCreateVoice, useDeleteVoice, useListAssets, usePreviewVoice, getListVoicesQueryKey } from "@workspace/api-client-react"
import { useQueryClient } from "@tanstack/react-query"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { PageLoading, ErrorState, EmptyState } from "@/components/shared"
import { formatDate } from "@/lib/utils"
import { Plus, Trash2, Mic, Play, Loader2, Music } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"

export default function VoicesPage() {
  const queryClient = useQueryClient()
  
  const { data: voices, isLoading, error, refetch } = useListVoices({
    query: { queryKey: getListVoicesQueryKey(), refetchInterval: 5000 }
  })
  
  const { data: assets } = useListAssets({ kind: "voice_sample" })
  
  const createVoice = useCreateVoice({ mutation: { onSuccess: () => queryClient.invalidateQueries({ queryKey: getListVoicesQueryKey() }) } })
  const deleteVoice = useDeleteVoice({ mutation: { onSuccess: () => queryClient.invalidateQueries({ queryKey: getListVoicesQueryKey() }) } })
  const previewVoice = usePreviewVoice({ mutation: { onSuccess: () => queryClient.invalidateQueries({ queryKey: getListVoicesQueryKey() }) } })

  const [isNewDialogOpen, setIsNewDialogOpen] = useState(false)
  const [newName, setNewName] = useState("")
  const [selectedSamples, setSelectedSamples] = useState<string[]>([])

  const [previewingId, setPreviewingId] = useState<string | null>(null)
  const [previewText, setPreviewText] = useState("Hello! This is a test of my cloned voice.")

  if (isLoading) return <PageLoading />
  if (error) return <ErrorState error={error} retry={() => refetch()} />

  const handleCreate = () => {
    if (!newName.trim() || selectedSamples.length === 0) return
    createVoice.mutate({ data: { name: newName, sampleAssetIds: selectedSamples } })
    setIsNewDialogOpen(false)
    setNewName("")
    setSelectedSamples([])
  }

  const voiceSamples = assets || []

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Voices</h1>
          <p className="text-muted-foreground mt-1">Train and manage your AI voice clones.</p>
        </div>
        <Button onClick={() => setIsNewDialogOpen(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Clone Voice
        </Button>
      </div>

      <Dialog open={isNewDialogOpen} onOpenChange={setIsNewDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Clone a New Voice</DialogTitle>
          </DialogHeader>
          <div className="space-y-6 py-4">
            <div className="space-y-2">
              <Label>Voice Name</Label>
              <Input 
                placeholder="e.g. Studio Mic - Energetic" 
                value={newName} 
                onChange={(e) => setNewName(e.target.value)} 
              />
            </div>
            <div className="space-y-2">
              <Label>Select Samples (at least 1)</Label>
              {voiceSamples.length === 0 ? (
                <div className="text-sm text-muted-foreground p-4 bg-muted/50 rounded-md border border-dashed">
                  No voice samples found. Please upload them in the Library first.
                </div>
              ) : (
                <div className="max-h-60 overflow-y-auto space-y-2 p-1">
                  {voiceSamples.map(sample => (
                    <div key={sample.id} className="flex items-center space-x-3 p-2 border rounded-md hover:bg-muted/50 transition-colors">
                      <Checkbox 
                        id={sample.id} 
                        checked={selectedSamples.includes(sample.id)}
                        onCheckedChange={(checked) => {
                          if (checked) setSelectedSamples([...selectedSamples, sample.id])
                          else setSelectedSamples(selectedSamples.filter(id => id !== sample.id))
                        }}
                      />
                      <label htmlFor={sample.id} className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer flex-1 flex items-center gap-2">
                        <Music className="w-4 h-4 text-muted-foreground" />
                        {sample.name}
                      </label>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsNewDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleCreate} disabled={!newName.trim() || selectedSamples.length === 0 || createVoice.isPending}>
              {createVoice.isPending ? "Starting..." : "Start Training"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!previewingId} onOpenChange={(open) => !open && setPreviewingId(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Generate Preview</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <Label>Preview Text</Label>
            <Input 
              value={previewText} 
              onChange={(e) => setPreviewText(e.target.value)} 
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPreviewingId(null)}>Cancel</Button>
            <Button 
              onClick={() => {
                if (previewingId) {
                  previewVoice.mutate({ voiceId: previewingId, data: { text: previewText } })
                  setPreviewingId(null)
                }
              }}
              disabled={!previewText.trim() || previewVoice.isPending}
            >
              Generate
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {(!voices || voices.length === 0) ? (
        <EmptyState 
          title="No voices trained" 
          description="Upload some voice samples and train your first clone."
          action={<Button variant="outline" onClick={() => setIsNewDialogOpen(true)} className="mt-4"><Plus className="w-4 h-4 mr-2" />Clone Voice</Button>}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {voices.map((voice) => (
            <Card key={voice.id} className="flex flex-col h-full hover-elevate transition-colors relative overflow-hidden group">
              {voice.status === 'training' && (
                <div className="absolute top-0 left-0 right-0 h-1 bg-primary/20">
                  <div className="h-full bg-primary animate-[pulse_2s_ease-in-out_infinite]" style={{ width: '100%' }} />
                </div>
              )}
              
              <CardContent className="p-6 flex-1 flex flex-col">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${voice.status === 'ready' ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'}`}>
                      <Mic className="w-4 h-4" />
                    </div>
                    <h3 className="font-semibold text-lg text-foreground">{voice.name}</h3>
                  </div>
                  <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity" onClick={() => {
                    if (confirm("Delete this voice?")) deleteVoice.mutate({ voiceId: voice.id })
                  }}>
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
                
                <div className="mt-2 mb-6">
                  <Badge variant={
                    voice.status === 'ready' ? 'success' :
                    voice.status === 'failed' ? 'destructive' :
                    voice.status === 'training' ? 'default' : 'secondary'
                  }>
                    {voice.status === 'training' && <Loader2 className="w-3 h-3 mr-1 animate-spin" />}
                    {voice.status}
                  </Badge>
                  {voice.statusMessage && (
                    <p className="text-xs text-destructive mt-2">{voice.statusMessage}</p>
                  )}
                </div>
                
                <div className="mt-auto space-y-4">
                  {voice.previewAssetId && voice.status === 'ready' ? (
                    <div className="p-3 bg-muted/30 rounded-lg border border-border">
                      <p className="text-xs text-muted-foreground mb-2 font-medium uppercase tracking-wider">Latest Preview</p>
                      {/* We'd fetch the asset to get the objectPath, or the API might return the URL directly.
                          Wait, voice.previewAssetId is just the ID. We can't build the URL without the objectPath.
                          Actually, since we don't have the objectPath directly on the voice, we might not be able to play it inline unless we fetch it.
                          Let's assume there's an endpoint to get the asset or we just hide the player and show a "Generate Preview" button.
                      */}
                      <Button variant="secondary" className="w-full text-xs" onClick={() => setPreviewingId(voice.id)}>
                        <Play className="w-3 h-3 mr-2" /> Generate New Preview
                      </Button>
                    </div>
                  ) : (
                    voice.status === 'ready' && (
                      <Button variant="secondary" className="w-full" onClick={() => setPreviewingId(voice.id)}>
                        <Play className="w-4 h-4 mr-2" /> Generate Preview
                      </Button>
                    )
                  )}
                  
                  <div className="text-xs text-muted-foreground flex justify-between border-t border-border pt-4">
                    <span>{voice.provider} provider</span>
                    <span>{formatDate(voice.createdAt)}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
