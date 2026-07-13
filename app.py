// ... sauran code dinka na sama yana nan...

// MAYE GURBIN WANNAN FUNCTION GABA DAYA
function PhoneLogin({ onBack, onContinue }) {
  const [phone, setPhone] = useState("");
  const [step, setStep] = useState("phone"); // phone | otp
  const [otp, setOtp] = useState("");
  const [pinId, setPinId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // !!! MUHIMMI: Bayan gwaji ka cire wannan key ka saka shi a Render Environment Variables
  const TERMII_API_KEY = "tlv_Hn4rlapWW6cTRqdHB5sWSkIwSNepn-VSBab_mQ08blk"; 

  const formatPhone = (p) => p.startsWith("0") ? "234" + p.slice(1) : p;

  const sendOTP = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("https://api.ng.termii.com/api/sms/otp/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          api_key: TERMII_API_KEY,
          message_type: "NUMERIC",
          to: formatPhone(phone),
          from: "Zango",
          channel: "dnd",
          pin_attempts: 3,
          pin_length: 4,
          pin_placeholder: "< 1234 >",
          message_text: "Zango code: < 1234 >. Kada ka baiwa kowa.",
          pin_type: "NUMERIC"
        })
      });
      const data = await res.json();
      if(data.code === "ok"){
        setPinId(data.pinId);
        setStep("otp");
      } else {
        setError(data.message || "Ba a iya tura OTP ba. Duba balance");
      }
    } catch (e) {
      setError("Network error. Duba internet");
    }
    setLoading(false);
  };

  const verifyOTP = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("https://api.ng.termii.com/api/sms/otp/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          api_key: TERMII_API_KEY,
          pin_id: pinId,
          pin: otp
        })
      });
      const data = await res.json();
      if(data.verified === true){
        onContinue(phone.trim()); // Login yayi nasara
      } else {
        setError("Wrong code. Gwada kuma");
      }
    } catch (e) {
      setError("Verification failed");
    }
    setLoading(false);
  };

  if (step === "otp") {
    return (
      <div className="flex flex-col h-full" style={{ background: COLORS.ink, color: COLORS.paper }}>
        <TopBar title="Verify" onBack={() => setStep("phone")} />
        <div className="flex-1 flex flex-col justify-center px-8">
          <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 26 }}>Enter the code</div>
          <div className="mt-2 mb-6 text-sm" style={{ color: "#B9B9B5", fontFamily: "Inter" }}>
            Mun tura code zuwa {phone}
          </div>
          <input
            style={{ ...inputStyle(), background: "#1C1C1D", borderColor: "#39393A", color: COLORS.paper, textAlign: "center", letterSpacing: 4, fontFamily: "'IBM Plex Mono', monospace" }}
            placeholder="— — — —"
            value={otp}
            onChange={(e) => setOtp(e.target.value)}
            maxLength={4}
          />
          {error && <p className="text-xs mt-2" style={{color: COLORS.stop}}>{error}</p>}
          <div className="mt-6">
            <PrimaryButton disabled={loading || otp.length !== 4} onClick={verifyOTP} style={{ background: COLORS.paper, color: COLORS.ink }}>
              {loading ? "Verifying..." : "Continue"}
            </PrimaryButton>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full" style={{ background: COLORS.ink, color: COLORS.paper }}>
      <TopBar title="Phone Number" onBack={onBack} />
      <div className="flex-1 flex flex-col justify-center px-8">
        <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 26 }}>What's your number?</div>
        <div className="mt-2 mb-6 text-sm" style={{ color: "#B9B9B5", fontFamily: "Inter" }}>
          Za mu tura maka code ta SMS
        </div>
        <input
          style={{ ...inputStyle(), background: "#1C1C1D", borderColor: "#39393A", color: COLORS.paper }}
          placeholder="08012345678"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
        />
        {error && <p className="text-xs mt-2" style={{color: COLORS.stop}}>{error}</p>}
        <div className="mt-6">
          <PrimaryButton disabled={loading || phone.length < 10} onClick={sendOTP} style={{ background: COLORS.paper, color: COLORS.ink }}>
            {loading ? "Sending..." : "Continue"}
          </PrimaryButton>
        </div>
      </div>
    </div>
  );
}

// ... sauran code dinka na kasa yana nan...
