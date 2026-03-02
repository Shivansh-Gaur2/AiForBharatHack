import { useState } from "react";
import {
  Shield,
  Lock,
  FileText,
  Eye,
  UserCheck,
  AlertTriangle,
} from "lucide-react";
import { Card, CardTitle, Badge, Button, Input, Select, AlertBanner } from "@/components/ui";

/**
 * Security & Privacy management page.
 * This is largely informational in the frontend since the heavy lifting
 * (encryption, consent, audit) happens in the Security service.
 */
export function SecurityPage() {
  const [consentProfileId, setConsentProfileId] = useState("");
  const [consentGranted, setConsentGranted] = useState(false);

  function handleConsentSubmit(e: React.FormEvent) {
    e.preventDefault();
    // In production this would call the security service
    setConsentGranted(true);
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">
          Security & Privacy
        </h2>
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
            <h3 className="text-sm font-medium text-gray-900">
              AES-256 Encryption
            </h3>
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
            <h3 className="text-sm font-medium text-gray-900">
              Consent-Based Access
            </h3>
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
            <h3 className="text-sm font-medium text-gray-900">
              Full Audit Trail
            </h3>
            <p className="mt-1 text-xs text-gray-500">
              Every data access, modification, and consent event is logged
              in an immutable audit trail for regulatory compliance.
            </p>
          </div>
        </Card>
      </div>

      {/* Consent management mock */}
      <Card>
        <CardTitle className="mb-4">Consent Management</CardTitle>
        <form
          onSubmit={handleConsentSubmit}
          className="grid grid-cols-1 gap-4 sm:grid-cols-3"
        >
          <Input
            label="Profile ID"
            value={consentProfileId}
            onChange={(e) => setConsentProfileId(e.target.value)}
            placeholder="Enter borrower profile ID"
          />
          <Select
            label="Consent Scope"
            options={[
              { value: "CREDIT_ASSESSMENT", label: "Credit Assessment" },
              { value: "RISK_MONITORING", label: "Risk Monitoring" },
              { value: "GUIDANCE_GENERATION", label: "Guidance Generation" },
              { value: "DATA_SHARING", label: "Data Sharing" },
            ]}
          />
          <div className="flex items-end">
            <Button type="submit" className="w-full">
              Record Consent
            </Button>
          </div>
        </form>
        {consentGranted && (
          <AlertBanner
            variant="success"
            message="Consent recorded successfully."
            className="mt-4"
          />
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
                <p className="text-sm font-medium text-gray-900">
                  {policy.title}
                </p>
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

      {/* Recent audit log (mock) */}
      <Card>
        <CardTitle className="mb-4">Recent Audit Log</CardTitle>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-gray-500">
                <th className="pb-2 font-medium">Timestamp</th>
                <th className="pb-2 font-medium">Action</th>
                <th className="pb-2 font-medium">Resource</th>
                <th className="pb-2 font-medium">User</th>
                <th className="pb-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {[
                {
                  time: "2024-12-20 14:32:01",
                  action: "PROFILE_VIEWED",
                  resource: "profile-001",
                  user: "field-officer-01",
                  ok: true,
                },
                {
                  time: "2024-12-20 14:28:44",
                  action: "GUIDANCE_GENERATED",
                  resource: "guidance-042",
                  user: "system",
                  ok: true,
                },
                {
                  time: "2024-12-20 13:55:12",
                  action: "CONSENT_RECORDED",
                  resource: "profile-003",
                  user: "field-officer-02",
                  ok: true,
                },
                {
                  time: "2024-12-20 13:41:30",
                  action: "RISK_ASSESSED",
                  resource: "risk-017",
                  user: "system",
                  ok: true,
                },
                {
                  time: "2024-12-20 12:10:05",
                  action: "DATA_ACCESS_DENIED",
                  resource: "profile-005",
                  user: "external-api",
                  ok: false,
                },
              ].map((log, i) => (
                <tr key={i} className="text-gray-700">
                  <td className="py-2 font-mono text-xs">{log.time}</td>
                  <td className="py-2">
                    <Badge label={log.action} />
                  </td>
                  <td className="py-2 font-mono text-xs">{log.resource}</td>
                  <td className="py-2 text-xs">{log.user}</td>
                  <td className="py-2">
                    <Badge
                      label={log.ok ? "OK" : "DENIED"}
                      colorClass={
                        log.ok
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
      </Card>
    </div>
  );
}
