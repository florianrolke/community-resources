import { useState } from "react"
import { useListScripts, useCreateScript, useUpdateScript, useDeleteScript, getListScriptsQueryKey } from "@workspace/api-client-react"
import { useQueryClient } from "@tanstack/react-query"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { PageLoading, ErrorState, EmptyState } from "@/components/shared"
import { formatDate } from "@/lib/utils"
import { Plus, Edit2, Trash2, FileText, Check, X } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"

export default function ScriptsPage() {
  const queryClient = useQueryClient()
  const { data: scripts, isLoading, error, refetch } = useListScripts({
    query: { queryKey: getListScriptsQueryKey() }
  })
  
  const createScript = useCreateScript({ mutation: { onSuccess: () => queryClient.invalidateQueries({ queryKey: getListScriptsQueryKey() }) } })
  const updateScript = useUpdateScript({ mutation: { onSuccess: () => queryClient.invalidateQueries({ queryKey: getListScriptsQueryKey() }) } })
  const deleteScript = useDeleteScript({ mutation: { onSuccess: () => queryClient.invalidateQueries({ queryKey: getListScriptsQueryKey() }) } })

  const [isNewDialogOpen, setIsNewDialogOpen] = useState(false)
  const [newTitle, setNewTitle] = useState("")
  const [newBody, setNewBody] = useState("")

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState("")
  const [editBody, setEditBody] = useState("")

  if (isLoading) return <PageLoading />
  if (error) return <ErrorState error={error} retry={() => refetch()} />

  const handleCreate = () => {
    if (!newTitle.trim() || !newBody.trim()) return
    createScript.mutate({ data: { title: newTitle, body: newBody } })
    setIsNewDialogOpen(false)
    setNewTitle("")
    setNewBody("")
  }

  const startEdit = (script: any) => {
    setEditingId(script.id)
    setEditTitle(script.title)
    setEditBody(script.body)
  }

  const saveEdit = () => {
    if (!editingId || !editTitle.trim() || !editBody.trim()) return
    updateScript.mutate({ scriptId: editingId, data: { title: editTitle, body: editBody } })
    setEditingId(null)
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Scripts</h1>
          <p className="text-muted-foreground mt-1">Write and manage your voiceover narrations.</p>
        </div>
        <Button onClick={() => setIsNewDialogOpen(true)}>
          <Plus className="w-4 h-4 mr-2" />
          New Script
        </Button>
      </div>

      <Dialog open={isNewDialogOpen} onOpenChange={setIsNewDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Create Script</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <Input 
              placeholder="Script Title" 
              value={newTitle} 
              onChange={(e) => setNewTitle(e.target.value)} 
              className="font-medium text-lg"
            />
            <Textarea 
              placeholder="Write your narration here..." 
              value={newBody} 
              onChange={(e) => setNewBody(e.target.value)} 
              className="min-h-[300px] font-serif text-base leading-relaxed resize-y"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsNewDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleCreate} disabled={!newTitle.trim() || !newBody.trim() || createScript.isPending}>
              {createScript.isPending ? "Saving..." : "Save Script"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {(!scripts || scripts.length === 0) ? (
        <EmptyState 
          title="No scripts yet" 
          description="Create your first script to use in a video project."
          action={<Button variant="outline" onClick={() => setIsNewDialogOpen(true)} className="mt-4"><Plus className="w-4 h-4 mr-2" />New Script</Button>}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {scripts.map((script) => (
            <Card key={script.id} className="flex flex-col h-full hover-elevate transition-colors group">
              {editingId === script.id ? (
                <CardContent className="p-6 flex-1 flex flex-col gap-4">
                  <Input 
                    value={editTitle} 
                    onChange={(e) => setEditTitle(e.target.value)} 
                    className="font-semibold text-lg"
                  />
                  <Textarea 
                    value={editBody} 
                    onChange={(e) => setEditBody(e.target.value)} 
                    className="flex-1 min-h-[200px] font-serif"
                  />
                  <div className="flex justify-end gap-2 mt-2">
                    <Button variant="ghost" size="sm" onClick={() => setEditingId(null)}>
                      <X className="w-4 h-4 mr-2" /> Cancel
                    </Button>
                    <Button size="sm" onClick={saveEdit} disabled={updateScript.isPending}>
                      <Check className="w-4 h-4 mr-2" /> Save
                    </Button>
                  </div>
                </CardContent>
              ) : (
                <>
                  <CardContent className="p-6 flex-1 flex flex-col">
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center gap-2 text-primary">
                        <FileText className="w-5 h-5" />
                        <h3 className="font-semibold text-lg text-foreground line-clamp-1">{script.title}</h3>
                      </div>
                      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground" onClick={() => startEdit(script)}>
                          <Edit2 className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-destructive" onClick={() => {
                          if (confirm("Delete this script?")) deleteScript.mutate({ scriptId: script.id })
                        }}>
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                    
                    <div className="flex-1 relative overflow-hidden">
                      <p className="text-muted-foreground font-serif text-sm leading-relaxed line-clamp-6">
                        {script.body}
                      </p>
                      <div className="absolute bottom-0 left-0 right-0 h-12 bg-gradient-to-t from-card to-transparent pointer-events-none" />
                    </div>
                    
                    <div className="mt-4 pt-4 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
                      <span>{script.wordCount || script.body.split(/\s+/).length} words</span>
                      <span>{formatDate(script.updatedAt)}</span>
                    </div>
                  </CardContent>
                </>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
