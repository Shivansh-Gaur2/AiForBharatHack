import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";
import { profileApi } from "@/api";
import { Button, Card, CardTitle, Input, Select, AlertBanner } from "@/components/ui";
import { OccupationType, Season } from "@/types";
import type { CreateProfileRequest, CropInfo, SeasonalFactor } from "@/types";
import { formatEnum } from "@/lib/utils";

const OCCUPATION_OPTIONS = Object.values(OccupationType).map((v) => ({
  value: v,
  label: formatEnum(v),
}));

const SEASON_OPTIONS = Object.values(Season).map((v) => ({
  value: v,
  label: formatEnum(v),
}));

export function CreateProfilePage() {
  const navigate = useNavigate();

  // ── Personal Info ──
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("");
  const [location, setLocation] = useState("");
  const [district, setDistrict] = useState("");
  const [state, setState] = useState("");
  const [phone, setPhone] = useState("");

  // ── Livelihood ──
  const [occupation, setOccupation] = useState<OccupationType>(
    OccupationType.FARMER,
  );
  const [ownedAcres, setOwnedAcres] = useState("0");
  const [leasedAcres, setLeasedAcres] = useState("0");
  const [irrigatedPct, setIrrigatedPct] = useState("0");

  // ── Simple crop entry ──
  const [cropName, setCropName] = useState("");
  const [cropSeason, setCropSeason] = useState<Season>(Season.KHARIF);
  const [cropArea, setCropArea] = useState("");
  const [crops, setCrops] = useState<CropInfo[]>([]);

  // ── Seasonal factors ──
  const [seasonalFactors] = useState<SeasonalFactor[]>([
    { season: Season.KHARIF, income_multiplier: 1.3, expense_multiplier: 1.4, description: "Monsoon cultivation season" },
    { season: Season.RABI, income_multiplier: 1.1, expense_multiplier: 1.0, description: "Winter cultivation season" },
    { season: Season.ZAID, income_multiplier: 0.6, expense_multiplier: 0.6, description: "Summer off-season" },
  ]);

  const mutation = useMutation({
    mutationFn: (data: CreateProfileRequest) => profileApi.create(data),
    onSuccess: (profile) => navigate(`/profiles/${profile.profile_id}`),
  });

  function handleAddCrop() {
    if (!cropName || !cropArea) return;
    setCrops((prev) => [
      ...prev,
      {
        crop_name: cropName,
        season: cropSeason,
        area_acres: Number(cropArea),
        expected_yield_quintals: 0,
        expected_price_per_quintal: 0,
      },
    ]);
    setCropName("");
    setCropArea("");
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const payload: CreateProfileRequest = {
      personal_info: {
        name,
        age: Number(age),
        gender,
        location,
        district,
        state,
        phone: phone || undefined,
      },
      livelihood_info: {
        primary_occupation: occupation,
        secondary_occupations: [],
        land_details: {
          owned_acres: Number(ownedAcres),
          leased_acres: Number(leasedAcres),
          irrigated_percentage: Number(irrigatedPct),
        },
        crops,
        livestock: [],
        migration_patterns: [],
      },
      seasonal_factors: seasonalFactors,
    };

    mutation.mutate(payload);
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Link
        to="/profiles"
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Profiles
      </Link>

      <h2 className="text-xl font-bold text-gray-900">Create Borrower Profile</h2>

      {mutation.isError && (
        <AlertBanner
          variant="error"
          message={
            mutation.error instanceof Error
              ? mutation.error.message
              : "Failed to create profile"
          }
        />
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Personal Info */}
        <Card>
          <CardTitle className="mb-4">Personal Information</CardTitle>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input
              label="Full Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
            <Input
              label="Age"
              type="number"
              min={18}
              max={100}
              value={age}
              onChange={(e) => setAge(e.target.value)}
              required
            />
            <Select
              label="Gender"
              value={gender}
              onChange={(e) => setGender(e.target.value)}
              options={[
                { value: "male", label: "Male" },
                { value: "female", label: "Female" },
                { value: "other", label: "Other" },
              ]}
              required
            />
            <Input
              label="Phone"
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
            <Input
              label="Village/Town"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              required
            />
            <Input
              label="District"
              value={district}
              onChange={(e) => setDistrict(e.target.value)}
              required
            />
            <Input
              label="State"
              value={state}
              onChange={(e) => setState(e.target.value)}
              required
            />
          </div>
        </Card>

        {/* Livelihood */}
        <Card>
          <CardTitle className="mb-4">Livelihood Information</CardTitle>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Select
              label="Primary Occupation"
              value={occupation}
              onChange={(e) => setOccupation(e.target.value as OccupationType)}
              options={OCCUPATION_OPTIONS}
              required
            />
            <div /> {/* spacer */}
            <Input
              label="Owned Land (acres)"
              type="number"
              min={0}
              step={0.5}
              value={ownedAcres}
              onChange={(e) => setOwnedAcres(e.target.value)}
            />
            <Input
              label="Leased Land (acres)"
              type="number"
              min={0}
              step={0.5}
              value={leasedAcres}
              onChange={(e) => setLeasedAcres(e.target.value)}
            />
            <Input
              label="Irrigated (%)"
              type="number"
              min={0}
              max={100}
              value={irrigatedPct}
              onChange={(e) => setIrrigatedPct(e.target.value)}
            />
          </div>

          {/* Crop entry */}
          <div className="mt-6 border-t border-gray-100 pt-4">
            <h4 className="text-sm font-medium text-gray-700 mb-3">Crops</h4>
            <div className="flex gap-3 items-end">
              <Input
                label="Crop Name"
                value={cropName}
                onChange={(e) => setCropName(e.target.value)}
                placeholder="e.g., Paddy"
              />
              <Select
                label="Season"
                value={cropSeason}
                onChange={(e) => setCropSeason(e.target.value as Season)}
                options={SEASON_OPTIONS}
              />
              <Input
                label="Area (acres)"
                type="number"
                min={0}
                step={0.5}
                value={cropArea}
                onChange={(e) => setCropArea(e.target.value)}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleAddCrop}
              >
                Add
              </Button>
            </div>
            {crops.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {crops.map((c, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-700"
                  >
                    {c.crop_name} ({formatEnum(c.season)}, {c.area_acres}ac)
                    <button
                      type="button"
                      onClick={() =>
                        setCrops((prev) => prev.filter((_, idx) => idx !== i))
                      }
                      className="ml-1 text-green-400 hover:text-green-600"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </Card>

        {/* Submit */}
        <div className="flex justify-end gap-3">
          <Link to="/profiles">
            <Button type="button" variant="outline">
              Cancel
            </Button>
          </Link>
          <Button type="submit" loading={mutation.isPending}>
            Create Profile
          </Button>
        </div>
      </form>
    </div>
  );
}
