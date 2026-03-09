import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Shield,
  Lock,
  FileText,
  Eye,
  UserCheck,
  AlertTriangle,
  Search,
  RefreshCw,
  XCircle,
  Database,
} from "lucide-react";
import { Card, CardTitle, Badge, Button, Input, Select, AlertBanner } from "@/components/ui";
import { securityApi } from "@/api/security";
import type {
  ConsentDTO,
  AuditEntryDTO,
  RetentionPolicyDTO,
} from "@/api/security";

/**
 * Security & Privacy management page.
 * Fully wired to the Security service backend for consent management,
 * audit logging, data lineage tracking, and retention policies.
 */
export function SecurityPage() {
  const queryClient = useQueryClient();

  // --- Profile lookup state ---
  const [profileId, setProfileId] = useState("");
  const [activeProfileId, setActiveProfileId] = useState("");

  // --- Consent form state ---
  const [consentPurpose, setConsentPurpose] = useState("CREDIT_ASSESSMENT");

  // --- Tab state ---
  const [activeTab, setActiveTab] = useState<"consents" | "audit" | "usage" | "retention">("consents");

  // -----------------------------------------------------------------------
  // Queries — only fire when a profile is actively being inspected
  // -----------------------------------------------------------------------
  const consentsQuery = useQuery({
    queryKey: ["security", "consents", activeProfileId],
    queryFn: () => securityApi.getProfileConsents(activeProfileId),
    enabled: !!activeProfileId,
  });

  const auditQuery = useQuery({
    queryKey: ["security", "audit", activeProfileId],
    queryFn: () => securityApi.getAuditLog(activeProfileId, 50),
    enabled: !!activeProfileId && activeTab === "audit",
  });

  const usageQuery = useQuery({
    queryKey: ["security", "usage", activeProfileId],
    queryFn: () => securityApi.getDataUsage(activeProfileId),
    enabled: !!activeProfileId && activeTab === "usage",
  });

  const retentionQuery = useQuery({
    queryKey: ["security", "retention"],
    queryFn: () => securityApi.getRetentionPolicies(),
    enabled: activeTab === "retention",
  });

  const statsQuery = useQuery({
    queryKey: ["security", "stats"],
    queryFn: () => securityApi.stats(),
  });

  // -----------------------------------------------------------------------
  // Mutations
  // -----------------------------------------------------------------------
  const grantConsentMut = useMutation({
    mutationFn: () =>
      securityApi.grantConsent({
        profile_id: activeProfileId,
        purpose: consentPurpose,
        granted_by: "admin-ui",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["security", "consents", activeProfileId] });
      queryClient.invalidateQueries({ queryKey: ["security", "stats"] });
    },
  });

  const revokeConsentMut = useMutation({
    mutationFn: (consentId: string) =>
      securityApi.revokeConsent(consentId, { reason: "Revoked via admin UI" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["security", "consents", activeProfileId] });
      queryClient.invalidateQueries({ queryKey: ["security", "stats"] });
    },
  });

  const initRetentionMut = useMutation({
    mutationFn: () => securityApi.initializeRetentionPolicies(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["security", "retention"] });
    },
  });

  // -----------------------------------------------------------------------
  // Handlers
  // -----------------------------------------------------------------------
  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (profileId.trim()) setActiveProfileId(profileId.trim());
  }

  function handleGrantConsent(e: React.FormEvent) {
    e.preventDefault();
    if (!activeProfileId) return;
    grantConsentMut.mutate();
  }

  function formatTimestamp(ts: string) {
    return new Date(ts).toLocaleString("en-IN", {
      dateStyle: "medium",
      timeStyle: "medium",
    });
  }

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Security & Privacy</h2>
        <p className="text-sm text-gray-500">
          Data protection, consent management, audit trail, and compliance
        </p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="flex items-start gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100">
            <Lock className="h-5 w-5 text-green-700" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-gray-900">AES-256 Encryption</h3>
            <p className="mt-1 text-xs text-gray-500">
              Per-field encryption for PII (Aadhaar, PAN, bank accounts).
            </p>
          </div>
        </Card>
        <Card className="flex items-start gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100">
            <UserCheck className="h-5 w-5 text-blue-700" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-gray-900">Active Consents</h3>
            <p className="mt-1 text-2xl font-bold text-gray-900">
              {statsQuery.data?.active_consents ?? "—"}
            </p>
          </div>
        </Card>
        <Card className="flex items-start gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100">
            <FileText className="h-5 w-5 text-amber-700" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-gray-900">Audit Entries</h3>
            <p className="mt-1 text-2xl font-bold text-gray-900">
              {statsQuery.data?.total_audit_entries ?? "—"}
            </p>
          </div>
        </Card>
        <Card className="flex items-start gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-100">
            <Database className="h-5 w-5 text-purple-700" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-gray-900">Lineage Records</h3>
            <p className="mt-1 text-2xl font-bold text-gray-900">
              {statsQuery.data?.total_lineage_records ?? "—"}
            </p>
          </div>
        </Card>
      </div>

      {/* Profile search */}
      <Card>
        <form onSubmit={handleSearch} className="flex items-end gap-4">
          <Input
            label="Borrower Profile ID"
            value={profileId}
            onChange={(e) => setProfileId(e.target.value)}
            placeholder="Enter profile ID to inspect"
            className="flex-1"
          />
          <Button type="submit" disabled={!profileId.trim()}>
            <Search className="mr-2 h-4 w-4" />
            Inspect
          </Button>
        </form>
      </Card>

      {/* Tabs */}
      {activeProfileId && (
        <>
          <div className="flex gap-2 border-b">
            {(["consents", "audit", "usage", "retention"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 text-sm font-medium capitalize transition-colors ${
                  activeTab === tab
                    ? "border-b-2 border-brand-600 text-brand-700"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* ============ CONSENTS TAB ============ */}
          {activeTab === "consents" && (
            <div className="space-y-4">
              {/* Grant consent form */}
              <Card>
                <CardTitle className="mb-4">Grant Consent</CardTitle>
                <form onSubmit={handleGrantConsent} className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <Input label="Profile ID" value={activeProfileId} disabled />
                  <Select
                    label="Consent Purpose"
                    value={consentPurpose}
                    onChange={(e) => setConsentPurpose(e.target.value)}
                    options={[
                      { value: "CREDIT_ASSESSMENT", label: "Credit Assessment" },
                      { value: "RISK_SCORING", label: "Risk Scoring" },
                      { value: "DATA_SHARING_LENDER", label: "Data Sharing — Lender" },
                      { value: "DATA_SHARING_CREDIT_BUREAU", label: "Data Sharing — Credit Bureau" },
                      { value: "EARLY_WARNING_ALERTS", label: "Early Warning Alerts" },
                      { value: "GOVERNMENT_SCHEME_MATCHING", label: "Government Scheme Matching" },
                      { value: "RESEARCH_ANONYMIZED", label: "Research (Anonymized)" },
                    ]}
                  />
                  <div className="flex items-end">
                    <Button
                      type="submit"
                      className="w-full"
                      disabled={grantConsentMut.isPending}
                    >
                      {grantConsentMut.isPending ? "Granting…" : "Grant Consent"}
                    </Button>
                  </div>
                </form>
                {grantConsentMut.isSuccess && (
                  <AlertBanner variant="success" message="Consent granted successfully." className="mt-4" />
                )}
                {grantConsentMut.isError && (
                  <AlertBanner
                    variant="error"
                    message={`Failed: ${(grantConsentMut.error as Error).message}`}
                    className="mt-4"
                  />
                )}
              </Card>

              {/* Consent list */}
              <Card>
                <CardTitle className="mb-4">
                  Consent Records for {activeProfileId}
                </CardTitle>
                {consentsQuery.isLoading && (
                  <p className="text-sm text-gray-500">Loading consents…</p>
                )}
                {consentsQuery.data && consentsQuery.data.items.length === 0 && (
                  <p className="text-sm text-gray-400">No consent records found.</p>
                )}
                {consentsQuery.data && consentsQuery.data.items.length > 0 && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-left text-xs text-gray-500">
                          <th className="pb-2 font-medium">Purpose</th>
                          <th className="pb-2 font-medium">Status</th>
                          <th className="pb-2 font-medium">Granted</th>
                          <th className="pb-2 font-medium">Expires</th>
                          <th className="pb-2 font-medium">Version</th>
                          <th className="pb-2 font-medium">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {consentsQuery.data.items.map((c: ConsentDTO) => (
                          <tr key={c.consent_id} className="text-gray-700">
                            <td className="py-2">{c.purpose}</td>
                            <td className="py-2">
                              <Badge
                                label={c.status}
                                colorClass={
                                  c.status === "GRANTED"
                                    ? "bg-green-100 text-green-700"
                                    : c.status === "REVOKED"
                                      ? "bg-red-100 text-red-700"
                                      : "bg-gray-100 text-gray-700"
                                }
                              />
                            </td>
                            <td className="py-2 text-xs">{formatTimestamp(c.granted_at)}</td>
                            <td className="py-2 text-xs">{formatTimestamp(c.expires_at)}</td>
                            <td className="py-2 text-center">v{c.version}</td>
                            <td className="py-2">
                              {c.status === "GRANTED" && (
                                <Button
                                  variant="danger"
                                  size="sm"
                                  onClick={() => revokeConsentMut.mutate(c.consent_id)}
                                  disabled={revokeConsentMut.isPending}
                                >
                                  <XCircle className="mr-1 h-3 w-3" />
                                  Revoke
                                </Button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
            </div>
          )}

          {/* ============ AUDIT TAB ============ */}
          {activeTab === "audit" && (
            <Card>
              <CardTitle className="mb-4">Audit Log — {activeProfileId}</CardTitle>
              {auditQuery.isLoading && (
                <p className="text-sm text-gray-500">Loading audit log…</p>
              )}
              {auditQuery.data && auditQuery.data.items.length === 0 && (
                <p className="text-sm text-gray-400">No audit entries found.</p>
              )}
              {auditQuery.data && auditQuery.data.items.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-xs text-gray-500">
                        <th className="pb-2 font-medium">Timestamp</th>
                        <th className="pb-2 font-medium">Action</th>
                        <th className="pb-2 font-medium">Resource</th>
                        <th className="pb-2 font-medium">Actor</th>
                        <th className="pb-2 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {auditQuery.data.items.map((entry: AuditEntryDTO) => (
                        <tr key={entry.entry_id} className="text-gray-700">
                          <td className="py-2 font-mono text-xs">
                            {formatTimestamp(entry.timestamp)}
                          </td>
                          <td className="py-2">
                            <Badge label={entry.action} />
                          </td>
                          <td className="py-2 font-mono text-xs">
                            {entry.resource_type}/{entry.resource_id.slice(0, 8)}…
                          </td>
                          <td className="py-2 text-xs">{entry.actor_id}</td>
                          <td className="py-2">
                            <Badge
                              label={entry.success ? "OK" : "DENIED"}
                              colorClass={
                                entry.success
                                  ? "bg-green-100 text-green-700"
                                  : "bg-red-100 text-red-700"
                              }
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          )}

          {/* ============ DATA USAGE TAB ============ */}
          {activeTab === "usage" && (
            <Card>
              <CardTitle className="mb-4">Data Usage Summary — {activeProfileId}</CardTitle>
              {usageQuery.isLoading && (
                <p className="text-sm text-gray-500">Loading data usage…</p>
              )}
              {usageQuery.data && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                    <div className="rounded-lg border p-3 text-center">
                      <p className="text-2xl font-bold text-brand-700">
                        {usageQuery.data.active_consent_count}
                      </p>
                      <p className="text-xs text-gray-500">Active Consents</p>
                    </div>
                    <div className="rounded-lg border p-3 text-center">
                      <p className="text-2xl font-bold text-brand-700">
                        {usageQuery.data.total_data_accesses}
                      </p>
                      <p className="text-xs text-gray-500">Total Accesses</p>
                    </div>
                    <div className="rounded-lg border p-3 text-center">
                      <p className="text-2xl font-bold text-brand-700">
                        {usageQuery.data.services_with_access.length}
                      </p>
                      <p className="text-xs text-gray-500">Services with Access</p>
                    </div>
                    <div className="rounded-lg border p-3 text-center">
                      <p className="text-2xl font-bold text-brand-700">
                        {usageQuery.data.data_categories_stored.length}
                      </p>
                      <p className="text-xs text-gray-500">Data Categories</p>
                    </div>
                  </div>

                  {usageQuery.data.services_with_access.length > 0 && (
                    <div>
                      <h4 className="mb-2 text-sm font-medium text-gray-700">Services with Access</h4>
                      <div className="flex flex-wrap gap-2">
                        {usageQuery.data.services_with_access.map((svc) => (
                          <Badge key={svc} label={svc} colorClass="bg-blue-100 text-blue-700" />
                        ))}
                      </div>
                    </div>
                  )}

                  {usageQuery.data.pending_deletion_categories.length > 0 && (
                    <AlertBanner
                      variant="warning"
                      message={`Pending deletion: ${usageQuery.data.pending_deletion_categories.join(", ")}`}
                    />
                  )}
                </div>
              )}
            </Card>
          )}

          {/* ============ RETENTION TAB ============ */}
          {activeTab === "retention" && (
            <Card>
              <div className="mb-4 flex items-center justify-between">
                <CardTitle>Retention Policies</CardTitle>
                <Button
                  size="sm"
                  onClick={() => initRetentionMut.mutate()}
                  disabled={initRetentionMut.isPending}
                >
                  <RefreshCw className="mr-1 h-3 w-3" />
                  Initialize Defaults
                </Button>
              </div>
              {retentionQuery.isLoading && (
                <p className="text-sm text-gray-500">Loading retention policies…</p>
              )}
              {retentionQuery.data && retentionQuery.data.items.length === 0 && (
                <p className="text-sm text-gray-400">
                  No retention policies configured. Click "Initialize Defaults" to create them.
                </p>
              )}
              {retentionQuery.data && retentionQuery.data.items.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-xs text-gray-500">
                        <th className="pb-2 font-medium">Data Category</th>
                        <th className="pb-2 font-medium">Retention (days)</th>
                        <th className="pb-2 font-medium">Action</th>
                        <th className="pb-2 font-medium">Description</th>
                        <th className="pb-2 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {retentionQuery.data.items.map((p: RetentionPolicyDTO) => (
                        <tr key={p.policy_id} className="text-gray-700">
                          <td className="py-2 font-medium">{p.data_category}</td>
                          <td className="py-2">{p.retention_days.toLocaleString()}</td>
                          <td className="py-2">
                            <Badge
                              label={p.action}
                              colorClass={
                                p.action === "DELETE"
                                  ? "bg-red-100 text-red-700"
                                  : p.action === "ANONYMIZE"
                                    ? "bg-amber-100 text-amber-700"
                                    : "bg-blue-100 text-blue-700"
                              }
                            />
                          </td>
                          <td className="py-2 text-xs text-gray-500">{p.description}</td>
                          <td className="py-2">
                            <Badge
                              label={p.is_active ? "Active" : "Inactive"}
                              colorClass={
                                p.is_active
                                  ? "bg-green-100 text-green-700"
                                  : "bg-gray-100 text-gray-500"
                              }
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          )}
        </>
      )}

      {/* Data protection policies (always visible) */}
      <Card>
        <CardTitle className="mb-4">Data Protection Policies</CardTitle>
        <div className="space-y-3">
          {[
            {
              icon: <Shield className="h-4 w-4 text-brand-600" />,
              title: "DPDP Act 2023 Compliance",
              desc: "Data processing follows India's Digital Personal Data Protection Act requirements.",
              status: "Active",
            },
            {
              icon: <Eye className="h-4 w-4 text-brand-600" />,
              title: "Data Minimization",
              desc: "Only essential data is collected; PII is encrypted and access-controlled.",
              status: "Active",
            },
            {
              icon: <Lock className="h-4 w-4 text-brand-600" />,
              title: "Aadhaar Data Protection",
              desc: "Aadhaar numbers stored using per-field encryption with masked display.",
              status: "Active",
            },
            {
              icon: <AlertTriangle className="h-4 w-4 text-amber-600" />,
              title: "Data Retention",
              desc: "Borrower data retained for regulatory period, then securely purged.",
              status: "Configured",
            },
          ].map((policy, i) => (
            <div
              key={i}
              className="flex items-start gap-3 rounded-lg border border-gray-100 p-3"
            >
              <div className="mt-0.5">{policy.icon}</div>
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-900">{policy.title}</p>
                <p className="text-xs text-gray-500">{policy.desc}</p>
              </div>
              <Badge
                label={policy.status}
                colorClass={
                  policy.status === "Active"
                    ? "bg-green-100 text-green-700"
                    : "bg-amber-100 text-amber-700"
                }
              />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
