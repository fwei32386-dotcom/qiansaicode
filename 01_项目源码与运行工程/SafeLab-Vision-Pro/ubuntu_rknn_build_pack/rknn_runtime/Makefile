CXX ?= g++
RKNN_SDK ?=
RKNN_LIB_DIR ?= /usr/lib
RKNN_INCLUDE_DIR ?= $(RKNN_SDK)/include
WITH_RKNN ?= 0
TARGET ?= safelab_rknn_detect
SRCS := safelab_rknn_detect.cpp yolov8_postprocess.cpp
CXXFLAGS ?= -O2 -std=c++17 -Wall -Wextra
CPPFLAGS ?=
LDFLAGS ?=
LDLIBS ?=

ifeq ($(WITH_RKNN),1)
CPPFLAGS += -I$(RKNN_INCLUDE_DIR)
CPPFLAGS += -DSAFELAB_WITH_RKNN=1
LDFLAGS += -L$(RKNN_LIB_DIR)
LDLIBS += -lrknnrt
endif

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRCS) yolov8_postprocess.hpp
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $@ $(SRCS) $(LDFLAGS) $(LDLIBS)

clean:
	rm -f $(TARGET)
