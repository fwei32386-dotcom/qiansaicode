#pragma once

#include <array>
#include <string>
#include <vector>

namespace safelab {

struct RawDetection {
    float x1;
    float y1;
    float x2;
    float y2;
    float confidence;
    int class_id;
};

struct Detection {
    int frame_id;
    std::string source_type;
    std::string class_name;
    float confidence;
    std::array<int, 4> bbox;
    std::array<int, 2> center;
    int area;
    std::string model_name;
    float infer_time_ms;
};

struct LetterboxMeta {
    int source_width;
    int source_height;
    int input_width;
    int input_height;
};

const std::vector<std::string>& labels();
float dequantize_int8(int value, int zero_point, float scale);
std::vector<RawDetection> decode_yolov8_channel_major(
    const std::vector<float>& output,
    int channels,
    int anchors,
    const LetterboxMeta& meta,
    float confidence_threshold,
    float nms_iou_threshold);
std::vector<RawDetection> nms(const std::vector<RawDetection>& boxes, float iou_threshold);
Detection to_detection(
    const RawDetection& raw,
    int frame_id,
    const std::string& source_type,
    const std::string& model_name,
    float infer_time_ms,
    int frame_width,
    int frame_height);
Detection to_detection(
    const RawDetection& raw,
    int frame_id,
    const std::string& source_type,
    const std::string& model_name,
    float infer_time_ms,
    int frame_width,
    int frame_height,
    const std::vector<std::string>& label_names);
std::string detection_to_json(const Detection& detection);

}  // namespace safelab
