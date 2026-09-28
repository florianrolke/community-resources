import { useState } from "react"
import { useListProjects, useCreateProject, useDeleteProject, getListProjectsQueryKey } from "@workspace/api-client-react"
import { useQueryClient } from "@tanstack/react-query"
import { Link, useLocation } from "wouter"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { PageLoading, ErrorState, EmptyState } from "@/components/shared"
import { formatDate } from "@/lib/utils"
import { Plus, Trash2, Clapperboard, Clock, LayoutDashboard } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"

export default function ProjectsPage() {
  const queryClient = useQueryClient()
  const [, setLocation] = useLocation()
  
  const { data: projects, isLoading, error, refetch } = useListProjects({
    query: { queryKey: getListProjectsQueryKey(), refetchInterval: 10000 }
  })
  
  const createProject = useCreateProject({ 
    mutation: {
      onSuccess: (project) => {
        queryClient.invalidateQueries({ queryKey: getListProjectsQueryKey() })
        setLocation(`/projects/${project.id}`)
      }
    }
  })
  const deleteProject = useDeleteProject({ mutation: { onSuccess: () => queryClient.invalidateQueries({ queryKey: getListProjectsQueryKey() }) } })

  const [isNewDialogOpen, setIsNewDialogOpen] = useState(false)
  const [newTitle, setNewTitle] = useState("")

  if (isLoading) return <PageLoading />
  if (error) return <ErrorState error={error} retry={() => refetch()} />

  const handleCreate = () => {
    if (!newTitle.trim()) return
    createProject.mutate({ data: { title: newTitle } })
    setIsNewDialogOpen(false)
    setNewTitle("")
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Projects</h1>
          <p className="text-muted-foreground mt-1">Manage your video production pipelines.</p>
        </div>
        <Button onClick={() => setIsNewDialogOpen(true)}>
          <Plus className="w-4 h-4 mr-2" />
          New Project
        </Button>
      </div>

      <Dialog open={isNewDialogOpen} onOpenChange={setIsNewDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Create New Project</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <Input 
              placeholder="Project Title (e.g. Q3 Roadmap Update)" 
              value={newTitle} 
              onChange={(e) => setNewTitle(e.target.value)} 
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsNewDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleCreate} disabled={!newTitle.trim() || createProject.isPending}>
              {createProject.isPending ? "Creating..." : "Create Project"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {(!projects || projects.length === 0) ? (
        <EmptyState 
          title="No projects yet" 
          description="Create a project to start assembling your video."
          action={<Button variant="outline" onClick={() => setIsNewDialogOpen(true)} className="mt-4"><Plus className="w-4 h-4 mr-2" />New Project</Button>}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map((project) => (
            <Card key={project.id} className="flex flex-col h-full hover-elevate transition-colors group cursor-pointer" onClick={() => setLocation(`/projects/${project.id}`)}>
              <CardContent className="p-6 flex-1 flex flex-col">
                <div className="flex items-start justify-between mb-4">
                  <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center text-primary mb-3">
                    <Clapperboard className="w-6 h-6" />
                  </div>
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className="h-8 w-8 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity" 
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm("Delete this project?")) deleteProject.mutate({ projectId: project.id })
                    }}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
                
                <h3 className="font-semibold text-lg text-foreground mb-2 line-clamp-1">{project.title}</h3>
                
                <div className="mt-auto pt-4 flex items-center justify-between">
                  <Badge variant={
                    project.status === 'delivered' ? 'success' :
                    project.status === 'failed' ? 'destructive' :
                    project.status === 'processing' ? 'default' :
                    project.status === 'ready' ? 'secondary' : 'outline'
                  } className="capitalize">
                    {project.status}
                  </Badge>
                  
                  <div className="flex items-center text-xs text-muted-foreground">
                    <Clock className="w-3 h-3 mr-1" />
                    {formatDate(project.updatedAt)}
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
