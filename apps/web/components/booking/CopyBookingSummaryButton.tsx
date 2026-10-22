import { getBookingSummaryText } from "@calcom/features/bookings/lib/getBookingSummaryText";
import { useCopy } from "@calcom/lib/hooks/useCopy";
import { useLocale } from "@calcom/lib/hooks/useLocale";
import { Button } from "@calcom/ui/components/button";
import { showToast } from "@calcom/ui/components/toast";

export type CopyBookingSummaryButtonProps = {
  title: string;
  formattedDate: string;
  formattedTimeRange: string;
  formattedTimeZone: string;
  location?: string | null;
};

export function CopyBookingSummaryButton({
  title,
  formattedDate,
  formattedTimeRange,
  formattedTimeZone,
  location,
}: CopyBookingSummaryButtonProps) {
  const { t } = useLocale();
  const { copyToClipboard, isCopied } = useCopy();

  const handleClick = () => {
    const summary = getBookingSummaryText({
      title,
      formattedDate,
      formattedTimeRange,
      formattedTimeZone,
      location,
      t,
    });

    copyToClipboard(summary, {
      onSuccess: () => showToast(t("copied"), "success"),
      onFailure: () => showToast(t("something_went_wrong"), "error"),
    });
  };

  return (
    <Button
      color="secondary"
      StartIcon={isCopied ? "clipboard-check" : "clipboard"}
      data-testid="copy-booking-summary"
      onClick={handleClick}>
      {isCopied ? t("copied") : t("copy_summary")}
    </Button>
  );
}
