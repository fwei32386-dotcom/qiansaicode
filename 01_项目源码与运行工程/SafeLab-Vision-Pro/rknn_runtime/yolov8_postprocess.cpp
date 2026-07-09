#include "yolov8_postprocess.hpp"

#include <algorithm>
#include <cmath>
#include <sstream>
#include <stdexcept>

namespace safelab {

const std::vector<std::string>& labels() {
    static const std::vector<std::string> kLabels = {
        "person", "helmet", "vest", "goggles", "gloves", "fire", "smoke"};
    return kLabels;
}

float dequantize_int8(int value, int zero_point, float scale) {
    return static_cast<float>(value - zero_point) * scale;
}

namespace {

float letterbox_scale(const LetterboxMeta& meta) {
    return std::min(
        static_cast<float>(meta.input_width) / static_cast<float>(meta.source_width),
        static_cast<float>(meta.input_height) / static_cast<float>(meta.source_height));
}

float iou_xyxy(const RawDetection& a, const RawDetection& b) {
    const float ix1 = std::max(a.x1, b.x1);
    const float iy1 = std::max(a.y1, b.y1);
    const float ix2 = std::min(a.x2, b.x2);
    const float iy2 = std::min(a.y2, b.y2);
    const float iw = std::max(ix2 - ix1, 0.0f);
    const float ih = std::max(iy2 - iy1, 0.0f);
    const float intersection = iw * ih;
    const float area_a = std::max(a.x2 - a.x1, 0.0f) * std::max(a.y2 - a.y1, 0.0f);
    const float area_b = std::max(b.x2 - b.x1, 0.0f) * std::max(b.y2 - b.y1, 0.0f);
    const float denom = area_a + area_b - intersection;
    if (denom <= 0.0f) {
        return 0.0f;
    }
    return intersection / denom;
}

bool xywh_to_source_xyxy(
    float cx,
    float cy,
    float width,
    float height,
    const LetterboxMeta& meta,
    RawDetection* detection) {
    const float scale = letterbox_scale(meta);
    const float pad_x = (meta.input_width - meta.source_width * scale) / 2.0f;
    const float pad_y = (meta.input_height - meta.source_height * scale) / 2.0f;

    float x1 = (cx - width / 2.0f - pad_x) / scale;
    float y1 = (cy - height / 2.0f - pad_y) / scale;
    float x2 = (cx + width / 2.0f - pad_x) / scale;
    float y2 = (cy + height / 2.0f - pad_y) / scale;

    x1 = std::max(0.0f, std::min(x1, static_cast<float>(meta.source_width - 1)));
    y1 = std::max(0.0f, std::min(y1, static_cast<float>(meta.source_height - 1)));
    x2 = std::max(0.0f, std::min(x2, static_cast<float>(meta.source_width - 1)));
    y2 = std::max(0.0f, std::min(y2, static_cast<float>(meta.source_height - 1)));
    if (x2 <= x1 || y2 <= y1) {
        return false;
    }

    detection->x1 = x1;
    detection->y1 = y1;
    detection->x2 = x2;
    detection->y2 = y2;
    return true;
}

int clip_int(float value, int min_value, int max_value) {
    return std::max(min_value, std::min(static_cast<int>(std::round(value)), max_value));
}

std::string json_escape(const std::string& value) {
    std::ostringstream escaped;
    for (const char ch : value) {
        if (ch == '"' || ch == '\\') {
            escaped << '\\';
        }
        escaped << ch;
    }
    return escaped.str();
}

}  // namespace

std::vector<RawDetection> decode_yolov8_channel_major(
    const std::vector<float>& output,
    int channels,
    int anchors,
    const LetterboxMeta& meta,
    float confidence_threshold,
    float nms_iou_threshold) {
    if (channels <= 4) {
        throw std::runtime_error("YOLOv8 output must have box channels plus at least one class channel");
    }
    if (static_cast<int>(output.size()) != channels * anchors) {
        throw std::runtime_error("YOLOv8 output size does not match channels * anchors");
    }

    std::vector<RawDetection> candidates;
    const int class_count = channels - 4;
    for (int anchor = 0; anchor < anchors; ++anchor) {
        const float cx = output[0 * anchors + anchor];
        const float cy = output[1 * anchors + anchor];
        const float width = output[2 * anchors + anchor];
        const float height = output[3 * anchors + anchor];

        int best_class = 0;
        float best_score = output[4 * anchors + anchor];
        for (int class_id = 1; class_id < class_count; ++class_id) {
            const float score = output[(4 + class_id) * anchors + anchor];
            if (score > best_score) {
                best_score = score;
                best_class = class_id;
            }
        }
        if (best_score < confidence_threshold) {
            continue;
        }

        RawDetection detection{};
        if (!xywh_to_source_xyxy(cx, cy, width, height, meta, &detection)) {
            continue;
        }
        detection.confidence = best_score;
        detection.class_id = best_class;
        candidates.push_back(detection);
    }
    return nms(candidates, nms_iou_threshold);
}

std::vector<RawDetection> nms(const std::vector<RawDetection>& boxes, float iou_threshold) {
    std::vector<RawDetection> remaining = boxes;
    std::sort(remaining.begin(), remaining.end(), [](const RawDetection& a, const RawDetection& b) {
        return a.confidence > b.confidence;
    });

    std::vector<RawDetection> selected;
    while (!remaining.empty()) {
        const RawDetection current = remaining.front();
        selected.push_back(current);
        std::vector<RawDetection> next;
        for (size_t index = 1; index < remaining.size(); ++index) {
            const RawDetection& candidate = remaining[index];
            if (candidate.class_id != current.class_id || iou_xyxy(candidate, current) <= iou_threshold) {
                next.push_back(candidate);
            }
        }
        remaining.swap(next);
    }
    return selected;
}

Detection to_detection(
    const RawDetection& raw,
    int frame_id,
    const std::string& source_type,
    const std::string& model_name,
    float infer_time_ms,
    int frame_width,
    int frame_height) {
    return to_detection(
        raw,
        frame_id,
        source_type,
        model_name,
        infer_time_ms,
        frame_width,
        frame_height,
        labels());
}

Detection to_detection(
    const RawDetection& raw,
    int frame_id,
    const std::string& source_type,
    const std::string& model_name,
    float infer_time_ms,
    int frame_width,
    int frame_height,
    const std::vector<std::string>& label_names) {
    if (raw.class_id < 0 || raw.class_id >= static_cast<int>(label_names.size())) {
        throw std::runtime_error("class_id outside labels range");
    }
    const int x1 = clip_int(raw.x1, 0, frame_width - 1);
    const int y1 = clip_int(raw.y1, 0, frame_height - 1);
    const int x2 = clip_int(raw.x2, 0, frame_width - 1);
    const int y2 = clip_int(raw.y2, 0, frame_height - 1);
    Detection detection{};
    detection.frame_id = frame_id;
    detection.source_type = source_type;
    detection.class_name = label_names[raw.class_id];
    detection.confidence = raw.confidence;
    detection.bbox = {x1, y1, x2, y2};
    detection.center = {(x1 + x2) / 2, (y1 + y2) / 2};
    detection.area = std::max(x2 - x1, 0) * std::max(y2 - y1, 0);
    detection.model_name = model_name;
    detection.infer_time_ms = infer_time_ms;
    return detection;
}

std::string detection_to_json(const Detection& detection) {
    std::ostringstream json;
    json << "{";
    json << "\"frame_id\":" << detection.frame_id << ",";
    json << "\"source_type\":\"" << json_escape(detection.source_type) << "\",";
    json << "\"class_name\":\"" << json_escape(detection.class_name) << "\",";
    json << "\"confidence\":" << detection.confidence << ",";
    json << "\"bbox\":[" << detection.bbox[0] << "," << detection.bbox[1] << ","
         << detection.bbox[2] << "," << detection.bbox[3] << "],";
    json << "\"center\":[" << detection.center[0] << "," << detection.center[1] << "],";
    json << "\"area\":" << detection.area << ",";
    json << "\"model_name\":\"" << json_escape(detection.model_name) << "\",";
    json << "\"infer_time_ms\":" << detection.infer_time_ms;
    json << "}";
    return json.str();
}

}  // namespace safelab
