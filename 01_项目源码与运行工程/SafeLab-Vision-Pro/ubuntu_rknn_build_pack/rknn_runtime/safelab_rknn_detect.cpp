#include "yolov8_postprocess.hpp"

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <limits>
#include <tuple>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#if SAFELAB_WITH_RKNN
#include "rknn_api.h"
#endif

namespace {

struct Options {
    std::string model_path;
    std::string image_path;
    std::string output_path;
    int frame_id = 1;
    int frame_width = 1280;
    int frame_height = 720;
    float infer_time_ms = 0.0f;
    float confidence_threshold = 0.25f;
    std::string input_type = "uint8";
    bool pass_through = false;
    bool dump_output_stats = false;
    bool contract_mode = false;
    std::vector<safelab::RawDetection> raw_detections;
};

#if SAFELAB_WITH_RKNN
std::vector<safelab::RawDetection> run_rknn_detection(const Options& options);
#endif

void print_usage() {
    std::cout
        << "Usage:\n"
        << "  safelab_rknn_detect --contract [--output detections.jsonl]\n"
        << "  safelab_rknn_detect --model model.rknn --image frame.jpg --raw x1,y1,x2,y2,conf,class_id [--output detections.jsonl]\n"
        << "  safelab_rknn_detect --model model.rknn --image frame.rgb --frame-width 1280 --frame-height 720 [--input-type uint8|int8] [--pass-through] [--conf-threshold 0.25] [--dump-output-stats] [--output detections.jsonl]\n"
        << "\n"
        << "Without SAFELAB_WITH_RKNN this build emits SafeLab Detection JSONL from --contract/--raw.\n"
        << "With SAFELAB_WITH_RKNN=1 it loads a .rknn model and expects an already letterboxed 640x640 NHWC RGB frame blob.\n";
}

float parse_float(const std::string& value, const std::string& field) {
    char* end = nullptr;
    const float parsed = std::strtof(value.c_str(), &end);
    if (end == value.c_str() || *end != '\0') {
        throw std::runtime_error("invalid float for " + field + ": " + value);
    }
    return parsed;
}

int parse_int(const std::string& value, const std::string& field) {
    char* end = nullptr;
    const long parsed = std::strtol(value.c_str(), &end, 10);
    if (end == value.c_str() || *end != '\0') {
        throw std::runtime_error("invalid integer for " + field + ": " + value);
    }
    return static_cast<int>(parsed);
}

std::vector<std::string> split_csv(const std::string& value) {
    std::vector<std::string> parts;
    std::stringstream stream(value);
    std::string part;
    while (std::getline(stream, part, ',')) {
        parts.push_back(part);
    }
    return parts;
}

safelab::RawDetection parse_raw_detection(const std::string& value) {
    const std::vector<std::string> parts = split_csv(value);
    if (parts.size() != 6) {
        throw std::runtime_error("--raw expects x1,y1,x2,y2,confidence,class_id");
    }
    safelab::RawDetection raw{};
    raw.x1 = parse_float(parts[0], "x1");
    raw.y1 = parse_float(parts[1], "y1");
    raw.x2 = parse_float(parts[2], "x2");
    raw.y2 = parse_float(parts[3], "y2");
    raw.confidence = parse_float(parts[4], "confidence");
    raw.class_id = parse_int(parts[5], "class_id");
    return raw;
}

Options parse_args(int argc, char** argv) {
    Options options;
    for (int index = 1; index < argc; ++index) {
        const std::string arg = argv[index];
        auto require_value = [&](const std::string& flag) -> std::string {
            if (index + 1 >= argc) {
                throw std::runtime_error("missing value for " + flag);
            }
            ++index;
            return argv[index];
        };

        if (arg == "--help" || arg == "-h") {
            print_usage();
            std::exit(0);
        } else if (arg == "--contract") {
            options.contract_mode = true;
        } else if (arg == "--model") {
            options.model_path = require_value(arg);
        } else if (arg == "--image") {
            options.image_path = require_value(arg);
        } else if (arg == "--output") {
            options.output_path = require_value(arg);
        } else if (arg == "--frame-id") {
            options.frame_id = parse_int(require_value(arg), "frame-id");
        } else if (arg == "--frame-width") {
            options.frame_width = parse_int(require_value(arg), "frame-width");
        } else if (arg == "--frame-height") {
            options.frame_height = parse_int(require_value(arg), "frame-height");
        } else if (arg == "--infer-time-ms") {
            options.infer_time_ms = parse_float(require_value(arg), "infer-time-ms");
        } else if (arg == "--conf-threshold") {
            options.confidence_threshold = parse_float(require_value(arg), "conf-threshold");
        } else if (arg == "--input-type") {
            options.input_type = require_value(arg);
            if (options.input_type != "uint8" && options.input_type != "int8") {
                throw std::runtime_error("--input-type expects uint8 or int8");
            }
        } else if (arg == "--pass-through") {
            options.pass_through = true;
        } else if (arg == "--dump-output-stats") {
            options.dump_output_stats = true;
        } else if (arg == "--raw") {
            options.raw_detections.push_back(parse_raw_detection(require_value(arg)));
        } else if (options.model_path.empty()) {
            options.model_path = arg;
        } else if (options.image_path.empty()) {
            options.image_path = arg;
        } else {
            throw std::runtime_error("unknown argument: " + arg);
        }
    }
    return options;
}

std::vector<safelab::RawDetection> detections_for(const Options& options) {
    if (!options.raw_detections.empty()) {
        return options.raw_detections;
    }
    if (options.contract_mode) {
        safelab::RawDetection raw{};
        raw.x1 = 10.0f;
        raw.y1 = 20.0f;
        raw.x2 = 110.0f;
        raw.y2 = 220.0f;
        raw.confidence = 0.91f;
        raw.class_id = 0;
        return {raw};
    }
#if SAFELAB_WITH_RKNN
    return run_rknn_detection(options);
#else
    throw std::runtime_error("no RKNN SDK runner is compiled in; pass --contract or --raw for Detection JSONL output");
#endif
}

std::string model_name_for(const Options& options) {
    if (options.contract_mode && options.model_path.empty()) {
        return "safelab_yolov8n_rknn_contract_probe";
    }
    return "safelab_yolov8n_rknn";
}

int write_detections(const Options& options, const std::vector<safelab::Detection>& detections) {
    std::ostream* output = &std::cout;
    std::ofstream file;
    if (!options.output_path.empty()) {
        file.open(options.output_path);
        if (!file) {
            throw std::runtime_error("cannot open output: " + options.output_path);
        }
        output = &file;
    }
    for (const safelab::Detection& detection : detections) {
        *output << safelab::detection_to_json(detection) << "\n";
    }
    return 0;
}

std::vector<unsigned char> read_binary_file(const std::string& path) {
    std::ifstream file(path, std::ios::binary);
    if (!file) {
        throw std::runtime_error("cannot open file: " + path);
    }
    file.seekg(0, std::ios::end);
    const std::streamoff size = file.tellg();
    if (size <= 0) {
        throw std::runtime_error("empty file: " + path);
    }
    file.seekg(0, std::ios::beg);
    std::vector<unsigned char> data(static_cast<size_t>(size));
    file.read(reinterpret_cast<char*>(data.data()), size);
    return data;
}

#if SAFELAB_WITH_RKNN
std::string dims_to_string(const rknn_tensor_attr& attr) {
    std::ostringstream stream;
    stream << "[";
    for (uint32_t i = 0; i < attr.n_dims; ++i) {
        if (i > 0) {
            stream << ",";
        }
        stream << attr.dims[i];
    }
    stream << "]";
    return stream.str();
}

void log_tensor_attr(const char* prefix, const rknn_tensor_attr& attr) {
    std::cerr
        << prefix
        << " index=" << attr.index
        << " name=" << attr.name
        << " dims=" << dims_to_string(attr)
        << " n_elems=" << attr.n_elems
        << " size=" << attr.size
        << " fmt=" << get_format_string(attr.fmt)
        << " type=" << get_type_string(attr.type)
        << " qnt=" << get_qnt_type_string(attr.qnt_type)
        << " zp=" << attr.zp
        << " scale=" << attr.scale
        << " w_stride=" << attr.w_stride
        << " size_with_stride=" << attr.size_with_stride
        << "\n";
}

void dump_output_stats(const std::vector<float>& output, int channels, int anchors) {
    std::cerr << "RKNN output stats: channels=" << channels << " anchors=" << anchors << "\n";
    for (int channel = 0; channel < channels; ++channel) {
        float min_value = std::numeric_limits<float>::infinity();
        float max_value = -std::numeric_limits<float>::infinity();
        double sum = 0.0;
        int max_anchor = 0;
        for (int anchor = 0; anchor < anchors; ++anchor) {
            const float value = output[channel * anchors + anchor];
            if (value < min_value) {
                min_value = value;
            }
            if (value > max_value) {
                max_value = value;
                max_anchor = anchor;
            }
            sum += value;
        }
        std::cerr
            << "  ch" << channel
            << " min=" << min_value
            << " max=" << max_value
            << " mean=" << (sum / anchors)
            << " max_anchor=" << max_anchor
            << "\n";
    }

    std::vector<std::tuple<float, int, int>> top_scores;
    for (int anchor = 0; anchor < anchors; ++anchor) {
        for (int class_id = 0; class_id < channels - 4; ++class_id) {
            top_scores.emplace_back(output[(4 + class_id) * anchors + anchor], anchor, class_id);
        }
    }
    std::sort(top_scores.begin(), top_scores.end(), [](const auto& a, const auto& b) {
        return std::get<0>(a) > std::get<0>(b);
    });
    const int top_count = std::min<int>(8, static_cast<int>(top_scores.size()));
    for (int rank = 0; rank < top_count; ++rank) {
        const float best_score = std::get<0>(top_scores[rank]);
        const int best_anchor = std::get<1>(top_scores[rank]);
        const int best_class = std::get<2>(top_scores[rank]);
        std::cerr
            << "  top score=" << best_score
            << " class=" << best_class
            << " anchor=" << best_anchor
            << " xywh=("
            << output[0 * anchors + best_anchor] << ","
            << output[1 * anchors + best_anchor] << ","
            << output[2 * anchors + best_anchor] << ","
            << output[3 * anchors + best_anchor] << ")\n";
    }
}

std::vector<safelab::RawDetection> run_rknn_detection(const Options& options) {
    if (options.model_path.empty() || options.image_path.empty()) {
        throw std::runtime_error("--model and --image are required for RKNN mode");
    }

    const std::vector<unsigned char> model = read_binary_file(options.model_path);
    const std::vector<unsigned char> input = read_binary_file(options.image_path);
    const size_t expected_input_size = 640 * 640 * 3;
    if (input.size() != expected_input_size) {
        throw std::runtime_error("RKNN mode currently expects a 640x640x3 NHWC RGB input blob; preprocess camera/JPEG frames before calling");
    }

    rknn_context ctx = 0;
    int ret = rknn_init(&ctx, const_cast<unsigned char*>(model.data()), static_cast<uint32_t>(model.size()), 0, nullptr);
    if (ret != RKNN_SUCC) {
        throw std::runtime_error("rknn_init failed: " + std::to_string(ret));
    }

    rknn_input_output_num io_num{};
    ret = rknn_query(ctx, RKNN_QUERY_IN_OUT_NUM, &io_num, sizeof(io_num));
    if (ret != RKNN_SUCC) {
        rknn_destroy(ctx);
        throw std::runtime_error("rknn_query IN_OUT_NUM failed: " + std::to_string(ret));
    }
    if (io_num.n_input != 1 || io_num.n_output != 1) {
        rknn_destroy(ctx);
        throw std::runtime_error("expected one RKNN input and one output");
    }

    rknn_tensor_attr input_attr{};
    input_attr.index = 0;
    ret = rknn_query(ctx, RKNN_QUERY_INPUT_ATTR, &input_attr, sizeof(input_attr));
    if (ret != RKNN_SUCC) {
        rknn_destroy(ctx);
        throw std::runtime_error("rknn_query INPUT_ATTR failed: " + std::to_string(ret));
    }
    rknn_tensor_attr output_attr{};
    output_attr.index = 0;
    ret = rknn_query(ctx, RKNN_QUERY_OUTPUT_ATTR, &output_attr, sizeof(output_attr));
    if (ret != RKNN_SUCC) {
        rknn_destroy(ctx);
        throw std::runtime_error("rknn_query OUTPUT_ATTR failed: " + std::to_string(ret));
    }
    if (options.dump_output_stats) {
        log_tensor_attr("RKNN input", input_attr);
        log_tensor_attr("RKNN output", output_attr);
    }

    rknn_input input_tensor{};
    input_tensor.index = 0;
    // Let RKNN convert normal RGB bytes to the model input by default. pass_through is
    // reserved for native quantized blobs when we need to debug the driver boundary.
    input_tensor.pass_through = options.pass_through ? 1 : 0;
    input_tensor.type = options.input_type == "int8" ? RKNN_TENSOR_INT8 : RKNN_TENSOR_UINT8;
    input_tensor.size = static_cast<uint32_t>(input.size());
    input_tensor.fmt = RKNN_TENSOR_NHWC;
    input_tensor.buf = const_cast<unsigned char*>(input.data());

    ret = rknn_inputs_set(ctx, 1, &input_tensor);
    if (ret != RKNN_SUCC) {
        rknn_destroy(ctx);
        throw std::runtime_error("rknn_inputs_set failed: " + std::to_string(ret));
    }
    ret = rknn_run(ctx, nullptr);
    if (ret != RKNN_SUCC) {
        rknn_destroy(ctx);
        throw std::runtime_error("rknn_run failed: " + std::to_string(ret));
    }

    rknn_output output_tensor{};
    output_tensor.want_float = 1;
    ret = rknn_outputs_get(ctx, 1, &output_tensor, nullptr);
    if (ret != RKNN_SUCC) {
        rknn_destroy(ctx);
        throw std::runtime_error("rknn_outputs_get failed: " + std::to_string(ret));
    }

    const int channels = static_cast<int>(safelab::labels().size()) + 4;
    const int anchors = static_cast<int>(output_attr.n_elems) / channels;
    if (anchors <= 0 || output_attr.n_elems != static_cast<uint32_t>(channels * anchors)) {
        rknn_outputs_release(ctx, 1, &output_tensor);
        rknn_destroy(ctx);
        throw std::runtime_error("RKNN output element count cannot be decoded as YOLOv8 [11,anchors]");
    }
    const size_t output_count = static_cast<size_t>(channels * anchors);
    const float* output_data = static_cast<const float*>(output_tensor.buf);
    std::vector<float> output(output_data, output_data + output_count);
    rknn_outputs_release(ctx, 1, &output_tensor);
    rknn_destroy(ctx);

    if (options.dump_output_stats) {
        // These stats expose whether the RKNN output is channel-major YOLO data or a
        // native/strided layout, which is the current suspect behind zero detections.
        dump_output_stats(output, channels, anchors);
    }

    return safelab::decode_yolov8_channel_major(
        output,
        channels,
        anchors,
        safelab::LetterboxMeta{options.frame_width, options.frame_height, 640, 640},
        options.confidence_threshold,
        0.45f);
}
#endif

}  // namespace

int main(int argc, char** argv) {
    try {
        const Options options = parse_args(argc, argv);
        const std::vector<safelab::RawDetection> raw_detections = detections_for(options);
        std::vector<safelab::Detection> detections;
        for (const safelab::RawDetection& raw : raw_detections) {
            detections.push_back(safelab::to_detection(
                raw,
                options.frame_id,
                "camera",
                model_name_for(options),
                options.infer_time_ms,
                options.frame_width,
                options.frame_height));
        }
        return write_detections(options, detections);
    } catch (const std::exception& error) {
        std::cerr << "safelab_rknn_detect: " << error.what() << "\n";
        std::cerr << "Run with --help for usage.\n";
        return 2;
    }
}
