# Pass USER_C_MODULES=/absolute/path/to/backends/circuitpython
CJ_MOD_DIR := $(USERMOD_DIR)
CJ_ROOT := $(abspath $(CJ_MOD_DIR)/../../..)
SRC_USERMOD_C += $(CJ_MOD_DIR)/modcrankjam.c
SRC_USERMOD_LIB_C += $(CJ_MOD_DIR)/formatter.c
SRC_USERMOD_LIB_CXX += $(CJ_MOD_DIR)/floatparse.cpp
$(BUILD)/crankjam/floatparse.o: CXXFLAGS += -std=gnu++17 -fno-exceptions -fno-rtti -Wno-error=float-equal -Wno-error=double-promotion
SRC_USERMOD_LIB_C += $(CJ_MOD_DIR)/core_runtime.c $(CJ_MOD_DIR)/core_graphics.c $(CJ_MOD_DIR)/core_sound.c
CJ_LUA_NAMES := lapi lcode lctype ldebug ldo ldump lfunc lgc llex lmem lobject lopcodes lparser lstate lstring ltable ltm lundump lvm lzio lauxlib lbaselib lmathlib lstrlib ltablib lutf8lib
SRC_USERMOD_LIB_C += $(addprefix $(CJ_MOD_DIR)/lua_,$(addsuffix .c,$(CJ_LUA_NAMES)))
CFLAGS_USERMOD += -I$(CJ_ROOT)/include -I$(CJ_ROOT)/src -I$(CJ_ROOT)/vendor/lua-5.4.9/src
# Upstream Lua intentionally performs these conversions; scope exceptions ONLY
# to the unmodified core/Lua, not CP or our binding.
$(BUILD)/crankjam/core_%.o $(BUILD)/crankjam/lua_%.o: CFLAGS += -Wno-error=double-promotion -Wno-error=float-conversion -Wno-error=float-equal
$(BUILD)/crankjam/formatter.o: CFLAGS += -Wno-error=double-promotion -Wno-error=float-conversion -Wno-error=float-equal -Wno-error=sign-compare
# RP2350 CP defaults to single-precision constants, but Lua/stb use doubles.
# Restore standard C literal semantics ONLY for module core/Lua/formatter.
ifeq ($(CHIP_VARIANT),RP2350)
$(BUILD)/crankjam/%.o: CFLAGS += -fstack-usage
$(BUILD)/crankjam/%.o: CXXFLAGS += -fstack-usage
$(BUILD)/crankjam/floatparse.o: CXXFLAGS += -fno-single-precision-constant
SRC_USERMOD_LIB_C += $(CJ_MOD_DIR)/pico_double_math.c
CFLAGS_USERMOD += -I$(TOP)/ports/raspberrypi/sdk
LIBS += -lm
$(BUILD)/crankjam/pico_double_math.o: CFLAGS += -fno-single-precision-constant -Wno-error=double-promotion -Wno-error=float-equal -Wno-error=missing-prototypes -Wno-error=sign-compare
$(BUILD)/crankjam/core_%.o $(BUILD)/crankjam/lua_%.o $(BUILD)/crankjam/formatter.o: CFLAGS += -fno-single-precision-constant
endif
