interface AlertBannerProps {
  type: "success" | "danger" | "warning" | "info";
  message: string;
  onClose: () => void;
}

export default function AlertBanner({ type, message, onClose }: AlertBannerProps) {
  return (
    <div className={`alert alert-${type} alert-dismissible fade show`} role="alert">
      {message}
      <button type="button" className="btn-close" aria-label="Close" onClick={onClose}></button>
    </div>
  );
}
