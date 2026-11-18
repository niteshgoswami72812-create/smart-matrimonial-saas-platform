
import { useEffect, useState } from "react";
import api from "./api";
import "./Subscription.css";

const PLANS_API = "/api/profiles/subscription-plans/";
const SUBSCRIPTION_API = "/api/accounts/my-subscription/";
const CREATE_ORDER_API = "/api/accounts/subscription/create-order/";
const VERIFY_PAYMENT_API = "/api/accounts/subscription/verify-payment/";

const formatCurrency = (value) => {
  const amount = Number(value || 0);

  return `₹${amount.toLocaleString("en-IN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
};

const formatDate = (value) => {
  if (!value) return "Not available";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return String(value);

  return date.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
};

const getApiErrorMessage = (error, fallback) => {
  const data = error?.response?.data;

  if (typeof data === "string") return data;

  if (data?.error) return data.error;
  if (data?.detail) return data.detail;

  if (data && typeof data === "object") {
    const messages = Object.entries(data).map(([field, value]) => {
      const message = Array.isArray(value)
        ? value.join(", ")
        : typeof value === "string"
          ? value
          : JSON.stringify(value);

      return `${field}: ${message}`;
    });

    if (messages.length) return messages.join(" | ");
  }

  return error?.message || fallback;
};

const getPlanList = (data) => {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.results)) return data.results;
  return [];
};

const loadRazorpayScript = () => {
  return new Promise((resolve) => {
    if (window.Razorpay) {
      resolve(true);
      return;
    }

    const script = document.createElement("script");

    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;

    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);

    document.body.appendChild(script);
  });
};

function Subscription({ username }) {
  const [plans, setPlans] = useState([]);
  const [subscription, setSubscription] = useState(null);

  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState("");
  const [actionError, setActionError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const [processingPlanId, setProcessingPlanId] = useState(null);

  // Load plans and current subscription.
  const loadSubscriptionData = async () => {
    setLoading(true);
    setPageError("");

    try {
      const [plansResponse, subscriptionResponse] = await Promise.all([
        api.get(PLANS_API),

        api.get(SUBSCRIPTION_API).catch((error) => {
          // A 404 means this tenant has no subscription yet.
          if (error.response?.status === 404) {
            return { data: null };
          }

          throw error;
        }),
      ]);

      setPlans(getPlanList(plansResponse.data));
      setSubscription(subscriptionResponse.data || null);
    } catch (error) {
      setPageError(
        getApiErrorMessage(
          error,
          "Unable to load subscription information.",
        ),
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSubscriptionData();
  }, []);

  // Find the current plan name.
  const getCurrentPlanName = () => {
    const planValue = subscription?.plan;

    if (planValue && typeof planValue === "object") {
      return (
        planValue.name ||
        planValue.plan_name ||
        subscription?.plan_name ||
        "Current Plan"
      );
    }

    const matchedPlan = plans.find(
      (plan) => String(plan.id) === String(planValue),
    );

    if (matchedPlan) return matchedPlan.name;

    if (
      typeof planValue === "string" &&
      planValue.trim() &&
      Number.isNaN(Number(planValue))
    ) {
      return planValue;
    }

    return subscription?.plan_name || "Current Plan";
  };

  const currentPlanName = getCurrentPlanName();
  const subscriptionStatus = String(
    subscription?.status || "",
  ).toLowerCase();

  const isSubscriptionActive = subscriptionStatus === "active";

  const isCurrentPlan = (plan) => {
    const subscriptionPlanId =
      typeof subscription?.plan === "object"
        ? subscription.plan?.id
        : subscription?.plan;

    return (
      String(subscriptionPlanId) === String(plan.id) ||
      (
        currentPlanName.toLowerCase() ===
        String(plan.name || "").toLowerCase()
      )
    );
  };

  // Refresh subscription after successful payment verification.
  const refreshCurrentSubscription = async () => {
    try {
      const response = await api.get(SUBSCRIPTION_API);
      setSubscription(response.data || null);
    } catch (error) {
      console.error("Unable to refresh subscription:", error);
    }
  };

  // Verify payment on the backend.
  const verifyPayment = async (paymentResponse, order) => {
    setSuccessMessage("Payment response received. Verifying payment...");

    try {
      const verificationResponse = await api.post(
        VERIFY_PAYMENT_API,
        {
          razorpay_order_id:
            paymentResponse.razorpay_order_id ||
            order.razorpay_order_id,

          razorpay_payment_id:
            paymentResponse.razorpay_payment_id,

          razorpay_signature:
            paymentResponse.razorpay_signature,
        },
      );

      if (verificationResponse.data?.subscription) {
        setSubscription(verificationResponse.data.subscription);
      }

      setSuccessMessage(
        verificationResponse.data?.message ||
          "Payment verified and subscription activated successfully.",
      );

      await refreshCurrentSubscription();
    } catch (error) {
      setSuccessMessage("");

      setActionError(
        `Payment verification was not completed: ${getApiErrorMessage(
          error,
          "Please refresh your subscription status before trying again.",
        )}`,
      );
    } finally {
      setProcessingPlanId(null);
    }
  };

  // Create backend order and open Razorpay Checkout.
  const handleSubscribe = async (plan) => {
    setActionError("");
    setSuccessMessage("");

    if (Number(plan.price) <= 0) {
      setActionError(
        "This plan does not require online payment.",
      );
      return;
    }

    setProcessingPlanId(plan.id);

    try {
      const scriptLoaded = await loadRazorpayScript();

      if (!scriptLoaded) {
        throw new Error(
          "Razorpay Checkout could not be loaded. Please check your internet connection.",
        );
      }

      // Backend calculates the amount using the selected plan.
      const orderResponse = await api.post(CREATE_ORDER_API, {
        plan_id: plan.id,
      });

      const order = orderResponse.data;

      if (
        !order?.razorpay_order_id ||
        !order?.razorpay_key_id
      ) {
        throw new Error(
          "The backend did not return valid Razorpay order details.",
        );
      }

      const options = {
        key: order.razorpay_key_id,

        amount: order.amount,
        currency: order.currency || "INR",

        name: "Smart Matrimonial SaaS Platform",
        description: `${plan.name} Subscription`,

        order_id: order.razorpay_order_id,

        prefill: {
          name: username || "",
        },

        theme: {
          color: "#d94672",
        },

        handler: async (paymentResponse) => {
          await verifyPayment(paymentResponse, order);
        },

        modal: {
          ondismiss: () => {
            setProcessingPlanId(null);
          },
        },
      };

      const checkout = new window.Razorpay(options);

      checkout.on("payment.failed", (response) => {
        setActionError(
          response.error?.description ||
            "Payment failed. Please try again.",
        );

        setProcessingPlanId(null);
      });

      checkout.open();
    } catch (error) {
      setActionError(
        getApiErrorMessage(
          error,
          "Unable to start the payment process.",
        ),
      );

      setProcessingPlanId(null);
    }
  };

  return (
    <section className="subscription-page">
      <div className="subscription-heading">
        <div>
          <p className="subscription-eyebrow">
            SUBSCRIPTION MANAGEMENT
          </p>

          <h2>Subscription & Billing</h2>

          <p>
            Manage your tenant subscription and choose a plan
            for your matrimonial platform.
          </p>
        </div>

        <button
          type="button"
          className="subscription-refresh-button"
          onClick={loadSubscriptionData}
          disabled={loading || processingPlanId !== null}
        >
          ↻ Refresh
        </button>
      </div>

      {actionError && (
        <div className="subscription-alert subscription-alert-error" role="alert">
          {actionError}
        </div>
      )}

      {successMessage && (
        <div
          className="subscription-alert subscription-alert-success"
          role="status"
        >
          {successMessage}
        </div>
      )}

      {pageError && (
        <div className="subscription-alert subscription-alert-error" role="alert">
          {pageError}
        </div>
      )}

      {loading ? (
        <div className="subscription-loading">
          Loading subscription details...
        </div>
      ) : (
        <>
          {/* CURRENT SUBSCRIPTION */}
          <section className="current-subscription-card">
            <div className="current-subscription-header">
              <div>
                <span className="subscription-section-label">
                  CURRENT SUBSCRIPTION
                </span>

                <h3>
                  {subscription
                    ? currentPlanName
                    : "No Subscription"}
                </h3>
              </div>

              {subscription && (
                <span
                  className={`subscription-status ${
                    isSubscriptionActive ? "status-active" : "status-inactive"
                  }`}
                >
                  {subscription.status || "Unknown"}
                </span>
              )}
            </div>

            {subscription ? (
              <div className="subscription-details-grid">
                <div>
                  <span>Tenant</span>
                  <strong>
                    {typeof subscription.tenant === "object"
                      ? subscription.tenant?.name || "Tenant"
                      : subscription.tenant || "Not available"}
                  </strong>
                </div>

                <div>
                  <span>Plan Price</span>
                  <strong>
                    {formatCurrency(subscription.price)}
                  </strong>
                </div>

                <div>
                  <span>Start Date</span>
                  <strong>
                    {formatDate(subscription.start_date)}
                  </strong>
                </div>

                <div>
                  <span>End Date</span>
                  <strong>
                    {formatDate(subscription.end_date)}
                  </strong>
                </div>

                <div>
                  <span>Maximum Profiles</span>
                  <strong>
                    {subscription.max_profiles ?? "Not specified"}
                  </strong>
                </div>
              </div>
            ) : (
              <p className="subscription-empty-text">
                Your tenant does not have a subscription yet.
                Choose a plan below to get started.
              </p>
            )}
          </section>

          {/* AVAILABLE PLANS */}
          <div className="subscription-plans-heading">
            <div>
              <span className="subscription-section-label">
                AVAILABLE PLANS
              </span>

              <h3>Choose Your Plan</h3>
            </div>
          </div>

          {plans.length === 0 ? (
            <div className="subscription-empty-text">
              No subscription plans are currently available.
            </div>
          ) : (
            <div className="subscription-plans-grid">
              {plans.map((plan) => {
                const isFree = Number(plan.price) <= 0;
                const current = isCurrentPlan(plan);
                const processing =
                  String(processingPlanId) === String(plan.id);

                return (
                  <article
                    className={`subscription-plan-card ${
                      current && isSubscriptionActive
                        ? "subscription-plan-current"
                        : ""
                    }`}
                    key={plan.id}
                  >
                    {current && isSubscriptionActive && (
                      <span className="current-plan-badge">
                        CURRENT PLAN
                      </span>
                    )}

                    <h3>{plan.name}</h3>

                    <div className="subscription-plan-price">
                      {formatCurrency(plan.price)}
                    </div>

                    <p className="subscription-plan-duration">
                      For {plan.duration_days} days
                    </p>

                    <div className="subscription-plan-features">
                      <div>
                        <span>♙</span>
                        <span>
                          Up to {plan.max_profiles} profiles
                        </span>
                      </div>

                      <div>
                        <span>◷</span>
                        <span>
                          {plan.duration_days} days validity
                        </span>
                      </div>
                    </div>

                    <button
                      type="button"
                      className="subscription-buy-button"
                      disabled={
                        isFree ||
                        processingPlanId !== null
                      }
                      onClick={() => handleSubscribe(plan)}
                    >
                      {processing
                        ? "Processing..."
                        : isFree
                          ? "Free Plan"
                          : current && isSubscriptionActive
                            ? "Renew This Plan"
                            : "Choose Plan"}
                    </button>
                  </article>
                );
              })}
            </div>
          )}

          <div className="subscription-payment-note">
            <strong>Payment information</strong>

            <p>
              Payments are processed securely through Razorpay.
              Your subscription activates only after the backend
              verifies the payment.
            </p>

            <p>
              When a new payment is verified, your previous active
              subscription expires and the new plan starts from today.
            </p>
          </div>
        </>
      )}
    </section>
  );
}

export default Subscription;
