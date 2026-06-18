import { useCallback, useEffect, useState } from "react"
import { Activity, AlertTriangle, CheckCircle2, Clock3, Loader2, Play, RefreshCw, XCircle } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type Job = {
  id: number
  jobName: string
  status: string
  attempt: number
  maxAttempts: number
  errorMessage?: string | null
  createdAt?: string | null
  completedAt?: string | null
}

type QualityCheck = {
  key: string
  status: "ok" | "warning" | "error"
  affectedCount: number
  checkedAt: string
}

const headers = () => ({ Authorization: `Bearer ${localStorage.getItem("admin_token") || ""}` })

function statusIcon(status: string) {
  if (status === "succeeded" || status === "ok") return <CheckCircle2 className="h-4 w-4 text-emerald-600" />
  if (status === "failed" || status === "error") return <XCircle className="h-4 w-4 text-destructive" />
  if (status === "warning") return <AlertTriangle className="h-4 w-4 text-amber-600" />
  return <Clock3 className="h-4 w-4 text-muted-foreground" />
}

export default function AdminOperationsPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [checks, setChecks] = useState<QualityCheck[]>([])
  const [qualityStatus, setQualityStatus] = useState("not_run")
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [jobsResponse, qualityResponse] = await Promise.all([
        fetch("/api/v1/admin/jobs", { headers: headers() }),
        fetch("/api/v1/data-quality", { headers: headers() }),
      ])
      if (!jobsResponse.ok || !qualityResponse.ok) throw new Error("Operations data unavailable")
      const [jobData, qualityData] = await Promise.all([jobsResponse.json(), qualityResponse.json()])
      setJobs(jobData)
      setChecks(qualityData.checks || [])
      setQualityStatus(qualityData.status || "not_run")
    } catch {
      toast.error("Could not load job and data-quality status")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const runJob = async (jobName: string) => {
    setRunning(jobName)
    try {
      const response = await fetch(`/api/v1/admin/jobs/${jobName}/run`, {
        method: "POST",
        headers: headers(),
      })
      if (!response.ok) throw new Error("Queue request failed")
      toast.success(`${jobName} queued`)
      await load()
    } catch {
      toast.error("Could not queue the job")
    } finally {
      setRunning("")
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Operations</h1>
          <p className="text-sm text-muted-foreground">Background processing and revenue-data reliability.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh
          </Button>
          <Button onClick={() => void runJob("data_quality.refresh")} disabled={Boolean(running)}>
            {running === "data_quality.refresh" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
            Run Checks
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Activity className="h-5 w-5" />Data Quality <Badge variant="outline">{qualityStatus}</Badge></CardTitle>
        </CardHeader>
        <CardContent>
          {checks.length === 0 ? (
            <p className="text-sm text-muted-foreground">No checks have completed yet. Queue “Run Checks” and start the worker.</p>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {checks.map((check) => (
                <div key={check.key} className="flex items-center justify-between rounded-lg border p-3">
                  <div className="flex items-center gap-3">
                    {statusIcon(check.status)}
                    <div><p className="text-sm font-medium">{check.key.replace(/_/g, " ")}</p><p className="text-xs text-muted-foreground">{check.affectedCount} affected</p></div>
                  </div>
                  <Badge variant="outline">{check.status}</Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Recent Jobs</CardTitle>
          <Button size="sm" variant="outline" onClick={() => void runJob("analytics.aggregate_daily")} disabled={Boolean(running)}>
            <Play className="mr-2 h-4 w-4" />Aggregate Now
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>Job</TableHead><TableHead>Status</TableHead><TableHead>Attempt</TableHead><TableHead>Created</TableHead><TableHead>Error</TableHead></TableRow></TableHeader>
            <TableBody>
              {jobs.map((job) => (
                <TableRow key={job.id}>
                  <TableCell className="font-medium">{job.jobName}</TableCell>
                  <TableCell><span className="flex items-center gap-2">{statusIcon(job.status)}{job.status}</span></TableCell>
                  <TableCell>{job.attempt}/{job.maxAttempts}</TableCell>
                  <TableCell>{job.createdAt ? new Date(job.createdAt).toLocaleString() : "-"}</TableCell>
                  <TableCell className="max-w-72 truncate text-xs text-destructive">{job.errorMessage || "-"}</TableCell>
                </TableRow>
              ))}
              {!loading && jobs.length === 0 && <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground">No jobs queued yet.</TableCell></TableRow>}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
