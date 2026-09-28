import type { DialogProps as ControlledDialogProps } from "@calcom/features/components/controlled-dialog";
import { Dialog } from "@calcom/features/components/controlled-dialog";
import { useLocale } from "@calcom/lib/hooks/useLocale";
import { Button } from "@calcom/ui/components/button";
import { DialogClose, DialogContent, DialogFooter } from "@calcom/ui/components/dialog";
import QRCode from "qrcode";
import { useEffect, useState } from "react";

export function QRCodeDialog({
  permalink,
  eventTypeSlug,
  open,
  onOpenChange,
}: {
  permalink: string;
  eventTypeSlug: string;
} & Pick<ControlledDialogProps, "open" | "onOpenChange">) {
  const { t } = useLocale();
  const [dataUrl, setDataUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let isMounted = true;
    QRCode.toDataURL(permalink, { width: 256, margin: 2 }).then((url) => {
      if (isMounted) setDataUrl(url);
    });
    return () => {
      isMounted = false;
    };
  }, [open, permalink]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent type="creation" title={t("qr_code")} description={t("qr_code_dialog_description")}>
        <div className="flex flex-col items-center gap-4">
          <div className="border-default flex h-64 w-64 items-center justify-center rounded-md border p-2">
            {dataUrl && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={dataUrl} alt={permalink} width={240} height={240} />
            )}
          </div>
          <p className="w-full truncate text-center text-sm text-subtle">{permalink}</p>
        </div>
        <DialogFooter showDivider>
          <DialogClose />
          <Button
            type="button"
            StartIcon="download"
            disabled={!dataUrl}
            href={dataUrl ?? undefined}
            download={`${eventTypeSlug}-qr-code.png`}>
            {t("download")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
