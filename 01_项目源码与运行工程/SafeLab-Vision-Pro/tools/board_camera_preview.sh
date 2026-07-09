#!/bin/sh
set -u

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/reports"
REPORT_PATH="$REPORT_DIR/board_camera_preview.txt"
SNAPSHOT_PATH="$REPORT_DIR/board_camera_preview.jpg"
HTML_PATH="$REPORT_DIR/board_camera_preview.html"
DEVICE="${SAFELAB_CAMERA_DEVICE:-/dev/video-camera0}"
FALLBACK_DEVICE="/dev/video11"
ACTION="${1:-snapshot}"
LOOP_SECONDS="${2:-30}"

mkdir -p "$REPORT_DIR"
: > "$REPORT_PATH"

log() {
    echo "$1" | tee -a "$REPORT_PATH"
}

pick_device() {
    if [ -e "$DEVICE" ]; then
        echo "$DEVICE"
    elif [ -e "$FALLBACK_DEVICE" ]; then
        echo "$FALLBACK_DEVICE"
    else
        echo "$DEVICE"
    fi
}

write_html() {
    cat > "$HTML_PATH" <<HTML
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SafeLab Camera Preview</title>
  <style>
    body { margin: 0; font-family: Arial, sans-serif; background: #111827; color: white; }
    header { padding: 14px 18px; background: #0f172a; }
    main { padding: 18px; }
    img { width: 100%; max-width: 1280px; height: auto; border: 1px solid #475467; background: #000; }
    .meta { color: #cbd5e1; font-size: 14px; margin-top: 8px; }
  </style>
</head>
<body>
  <header><h1>SafeLab Camera Preview</h1></header>
  <main>
    <img id="preview" src="board_camera_preview.jpg" alt="OV13855 camera preview">
    <div class="meta">Auto-refreshes every 2 seconds when the snapshot loop is running.</div>
  </main>
  <script>
    setInterval(function () {
      document.getElementById("preview").src = "board_camera_preview.jpg?t=" + Date.now();
    }, 2000);
  </script>
</body>
</html>
HTML
}

snapshot_once() {
    device="$(pick_device)"
    if [ ! -e "$device" ]; then
        log "[FAIL] camera device missing: $device"
        return 1
    fi
    if ! command -v gst-launch-1.0 >/dev/null 2>&1; then
        log "[FAIL] gst-launch-1.0 is missing"
        return 1
    fi

    rm -f "$SNAPSHOT_PATH"
    if timeout 15 gst-launch-1.0 -q \
        v4l2src device="$device" num-buffers=1 \
        ! 'video/x-raw,format=NV12,width=4224,height=3136,framerate=30/1' \
        ! videoconvert \
        ! videoscale \
        ! 'video/x-raw,width=640,height=640' \
        ! jpegenc \
        ! filesink location="$SNAPSHOT_PATH" >> "$REPORT_PATH" 2>&1; then
        if [ -s "$SNAPSHOT_PATH" ]; then
            write_html
            size="$(wc -c < "$SNAPSHOT_PATH" | tr -d ' ')"
            log "[OK] snapshot: $SNAPSHOT_PATH ($size bytes)"
            log "[OK] preview html: $HTML_PATH"
            return 0
        fi
        log "[FAIL] snapshot file is empty"
        return 1
    fi

    log "[FAIL] gstreamer snapshot failed"
    return 1
}

snapshot_with_retry() {
    if snapshot_once; then
        return 0
    fi
    sleep 2
    snapshot_once
}

usage() {
    echo "Usage:"
    echo "  sh tools/board_camera_preview.sh info"
    echo "  sh tools/board_camera_preview.sh snapshot"
    echo "  sh tools/board_camera_preview.sh loop [seconds]"
    echo "  sh tools/board_camera_preview.sh live [seconds]"
}

log "SafeLab-Vision Pro Camera Preview"
log "Root: $ROOT_DIR"
log "Device: $(pick_device)"
log "Report: $REPORT_PATH"
log ""

case "$ACTION" in
    info)
        log "== Device Info =="
        if command -v v4l2-ctl >/dev/null 2>&1; then
            v4l2-ctl -d "$(pick_device)" --all 2>&1 | tee -a "$REPORT_PATH"
            v4l2-ctl -d "$(pick_device)" --list-formats-ext 2>&1 | tee -a "$REPORT_PATH"
        else
            log "v4l2-ctl missing"
        fi
        ;;
    snapshot)
        snapshot_once
        ;;
    loop)
        write_html
        end_time=$(( $(date +%s) + LOOP_SECONDS ))
        success_count=0
        while [ "$(date +%s)" -lt "$end_time" ]; do
            if snapshot_with_retry; then
                success_count=$((success_count + 1))
            fi
            sleep 3
        done
        if [ "$success_count" -gt 0 ] && [ -s "$SNAPSHOT_PATH" ]; then
            log "[OK] snapshot loop completed for $LOOP_SECONDS second(s), snapshots=$success_count"
        else
            log "[FAIL] snapshot loop completed without a valid snapshot"
            exit 1
        fi
        ;;
    live)
        device="$(pick_device)"
        log "Starting live preview for $LOOP_SECONDS second(s). This requires an attached display."
        timeout "$LOOP_SECONDS" gst-launch-1.0 \
            v4l2src device="$device" \
            ! 'video/x-raw,format=NV12,width=4224,height=3136,framerate=30/1' \
            ! videoconvert \
            ! videoscale \
            ! 'video/x-raw,width=1280,height=720' \
            ! autovideosink sync=false 2>&1 | tee -a "$REPORT_PATH"
        ;;
    -h|--help|help)
        usage
        ;;
    *)
        echo "Unknown action: $ACTION"
        usage
        exit 2
        ;;
esac
