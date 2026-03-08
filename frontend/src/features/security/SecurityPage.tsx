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
  XCircle,
} from "lucide-react";
import { securityApi } from "@/api/security";
import {
  Card,
  CardTitle,
  Badge,
  Button,
  Input,
  Select,
  AlertBanner,
  PageSpinner,
  EmptyState,
} from "@/components/ui";
import { formatDate } from "@/lib/utils";

const CONSENT_SCOPE_OPTIONS = [
  { value: "CREDIT_ASSESSMENT", label: "Credit Assessment" },
  { value: "RISK_MONITORING", label: "Risk Monitoring" },
  { value: "GUIDANCE_GENERATION", label: "Guidance Generation" },
  { value: "DATA_SHARING", label: "Data Sharing" },
];

const STATUS_COLORS: Record<string, string> = {
  ACTIVE: "bg-green-100 text-green-700",
  REVOKED: "bg-red-100 text-red-700",
  EXPIRED: "bg-gray-100 text-gray-500",
};

export function SecurityPage() {
  const [profileInput, setProfileInput] = useState("");
  const [activeProfileId, setActiveProfileId] = useState("");
  const [consentScope, setConsentScope] = useState("CREDIT_ASSESSMENT");
  const queryClient = useQueryClient();

  const {
    data: consentsData,
    isLoading: consentsLoading,
    error: consentsError,
  } = useQuery({
    queryKey: ["security-consents", activeProfileId],
    queryFn: () => securityApi.getProfileConsents(activeProfileId),
    enabled: !!activeProfileId,
    retry: false,
  });

  const {
    data: auditData,
    isLoading: auditLoading,
  } = useQuery({
    queryKey: ["security-audit", activeProfileId],
    queryFn: () => securityApi.getAuditLog(activeProfileId, 20),
    enabled: !!activeProfileId,
    retry: false,
  });

  const { data: retentionData } = useQuery({
    queryKey: ["security-retention"],
    queryFn: () => securityApi.getRetentionPolicies(),
    staleTime: 5 * 60 * 1000,
  });

  const grantMutation = useMutation({
    mutationFn: () =>
      securityApi.grantConsent({
        profile_id: activeProfileId,
        purpose: consentScope,
        granted_by: "field-officer",
        duration_days: 365,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["security-consents", activeProfileId],
      });
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (consentId: string) =>
      securityApi.revokeConsent(consentId, {
        reason: "Manual revocation",
        revoked_by: "field-officer",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["security-consents", activeProfileId],
      });
    },
  });

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setActiveProfileId(profileInput.trim());
  }

  function handleGrantConsent(e: React.FormEvent) {
    e.preventDefault();
    if (!activeProfileId) return;
    grantMutation.mutate();
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Security &amp; Privacy</h2>
        <p className="text-sm text-gray-500">
          Data protection, consent management, and compliance
        </p>
      </div>

      {/* Overview cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card className="flex items-start gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100">
            <Lock className="h-5 w-5 text-green-700" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-gray-900">AES-256 Encryption</h3>
            <p className="mt-1 text-xs text-gray-500">
              All personal data is encrypted at rest using AES-256-GCM with
              per-field encryption for sensitive identifiers like Aadhaar.
            </p>
          </div>
        </Card>
        <Card className="flex items-start gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100">
            <UserCheck className="h-5 w-5 text-blue-700" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-gray-900">Consent-Based Access</h3>
            <p className="mt-1 text-xs text-gray-500">
              Data access is governed by explicit borrower consent, tracked and
              auditable at the individual field level.
            </p>
          </div>
        </Card>
        <Card className="flex items-start gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100">
            <FileText className="h-5 w-5 text-amber-700" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-gray-900">Full Audit Trail</h3>
            <p className="mt-1 text-xs text-gray-500">
              Every data access, modification, and consent event is logged
              in an immutable audit trail for regulatory compliance.
            </p>
          </div>
        </Card>
      </div>

      {/* Profile search */}
      <Card>
        <form onSubmit={handleSearch} className="flex gap-3">
          <div className="flex-1">
            <Input
              placeholder="Enter borrower profile ID to view consent &amp; audit data…"
              value={profileInput}
              onChange={(e) => setProfileInput(e.target.value)}
            />
          </div>
          <Button type="submit" icon={<Search className="h-4 w-4" />}>
            Search
          </Button>
        </form>
      </Card>

      {/* Consent Management */}
      <Card>
        <CardTitle className="mb-4">Consent Management</CardTitle>

        <form
          onSubmit={handleGrantConsent}
          className="grid grid-cols-1 gap-4 sm:grid-cols-3 mb-6"
        >
          <Input
            label="Profile ID"
            value={profileInput}
            onChange={(e) => setProfileInput(e.target.value)}
            placeholder="Enter borrower profile ID"
          />
          <Select
            label="Consent Scope"
            value={consentScope}
            onChange={(e) => setConsentScope(e.target.value)}
            options={CONSENT_SCOPE_OPTIONS}
          />
          <div className="flex items-end">
            <Button
              type="submit"
              className="w-full"
              loading={grantMutation.isPending}
              disabled={!profileInput.trim()}
            >
              Grant Consent
            </Button>
          </div>
        </form>

        {grantMutation.isSuccess && (
          <AlertBanner
            variant="success"
            message="Consent recorded successfully."
            className="mb-4"
          />
        )}
        {grantMutation.isError && (
          <AlertBanner
            variant="error"
            message={
              grantMutation.error instanceof Error
                ? grantMutation.error.message
                : "Failed to record consent"
            }
            className="mb-4"
          />
        )}

        {activeProfileId && (
          <>
            {consentsLoading && <PageSpinner />}
            {consentsError && (
              <AlertBanner variant="error" message="Failed to load consents." />
            )}
            {consentsData && consentsData.count === 0 && (
              <EmptyState
                icon={<UserCheck className="h-8 w-8" />}
                title="No consents recorded"
                description="Grant a new consent above to get started."
              />
            )}
            {consentsData && consentsData.count > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs text-gray-500">
                      <th className="pb-2 font-medium">Purpose</th>
                      <th className="pb-2 font-medium">Status</th>
                      <th className="pb-2 font-medium">Granted</th>
                      <th className="pb-2 font-medium">Expires</th>
                      <th className="pb-2 font-medium">Granted By</th>
                      <th className="pb-2 font-medium" />
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {consentsData.items.map((c) => (
                      <tr key={c.consent_id} className="text-gray-700">
                        <td className="py-2 font-medium">{c.purpose}</td>
                        <td className="py-2">
                          <Badge
                            label={c.status}
                            colorClass={
                              STATUS_COLORS[c.status] ?? "bg-gray-100 text-gray-600"
                            }
                          />
                        </td>
                        <td className="py-2 text-xs">{formatDate(c.granted_at)}</td>
                        <td className="py-2 text-xs">{formatDate(c.expires_at)}</td>
                        <td className="py-2 text-xs">{c.granted_by || "—"}</td>
                        <td className="py-2">
                          {c.status === "ACTIVE" && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => revokeMutation.mutate(c.consent_id)}
                              loading={revokeMutation.isPending}
                              icon={<XCircle className="h-3.5 w-3.5" />}
                            >
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
          </>
        )}
      </Card>

      {/* Data protection policies */}
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
              desc: `Borrower data retained for regulatory period, then securely purged.${
                retentionData
                  ? ` ${retentionData.count} active polic${retentionData.count === 1 ? "y" : "ies"} configured.`
                  : ""
              }`,
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

      {/* Audit Log */}
      <Card>
        <CardTitle className="mb-4">Recent Audit Log</CardTitle>

        {!activeProfileId && (
          <p className="text-sm text-gray-400">
            Search for a profile above to view its audit log.
          </p>
        )}

        {activeProfileId && auditLoading && <PageSpinner />}

        {activeProfileId && auditData && auditData.count === 0 && (
          <EmptyState
            icon={<FileText className="h-8 w-8" />}
            title="No audit entries"
            description="No access events have been logged for this profile yet."
          />
        )}

        {activeProfileId && auditData && auditData.count > 0 && (
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
                {auditData.items.map((entry) => (
                  <tr key={entry.entry_id} className="text-gray-700">
                    <td className="py-2 font-mono text-xs">
                      {formatDate(entry.timestamp)}
                    </td>
                    <td className="py-2">
                      <Badge label={entry.action} />
                    </td>
                    <td className="py-2 font-mono text-xs">{entry.resource_id}</td>
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
    </div>
  );
}
