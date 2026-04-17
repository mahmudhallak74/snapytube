#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# SnapYTube Ultimate - سكريبت التشغيل (نسخة محسّنة)
# ═══════════════════════════════════════════════════════════════

clear
echo "╔══════════════════════════════════════════════════════════╗"
echo "║         SnapYTube Ultimate - بدء التشغيل                 ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# الانتقال إلى مجلد المشروع
cd ~/Snap/SnapYTube_Ultimate

# التأكد من وجود المجلدات الأساسية
echo "📁 التحقق من المجلدات..."
mkdir -p users logs cache templates static
echo "✅ المجلدات جاهزة"
echo ""

# تثبيت المتطلبات (إذا لزم)
if ! python -c "import flask" 2>/dev/null; then
    echo "📦 تثبيت المتطلبات..."
    pip install flask flask-cors yt-dlp
    echo "✅ تم تثبيت المتطلبات"
    echo ""
fi

# ⭐⭐⭐ قتل أي عملية تستخدم المنفذ 5001 (بطريقة مضمونة) ⭐⭐⭐
echo "🔍 التحقق من المنفذ 5001..."

# طريقة 1: استخدام fuser
fuser -k 5001/tcp 2>/dev/null

# طريقة 2: استخدام lsof (إذا fuser مش شغال)
if command -v lsof >/dev/null 2>&1; then
    PID=$(lsof -ti:5001 2>/dev/null)
    if [ -n "$PID" ]; then
        echo "⚠️ وجدت عملية تستخدم المنفذ 5001 (PID: $PID)، جاري إيقافها..."
        kill -9 $PID 2>/dev/null
    fi
fi

# طريقة 3: البحث عن عمليات python run.py
PIDS=$(ps aux | grep "[p]ython run.py" | awk '{print $2}')
if [ -n "$PIDS" ]; then
    echo "⚠️ وجدت عمليات Python قديمة، جاري إيقافها..."
    for pid in $PIDS; do
        kill -9 $pid 2>/dev/null
    done
fi

# انتظار لحظة
sleep 2
echo "✅ المنفذ 5001 أصبح جاهزاً"
echo ""

# ⭐⭐⭐ التأكد إنو المنفذ فعلاً فاضي ⭐⭐⭐
if lsof -ti:5001 >/dev/null 2>&1 || fuser 5001/tcp >/dev/null 2>&1; then
    echo "❌ خطأ: المنفذ 5001 ما زال محجوزاً!"
    echo "   جرب تشغل: killall python"
    echo "   أو غير المنفذ في config.py"
    exit 1
fi

# تشغيل السيرفر في الخلفية
echo "🚀 تشغيل SnapYTube Ultimate..."
python run.py &
SERVER_PID=$!
echo "✅ السيرفر يعمل (PID: $SERVER_PID)"
echo ""

# انتظار 5 ثواني لتجهيز السيرفر (بدل 3)
echo "⏳ انتظار 5 ثواني لتجهيز السيرفر..."
sleep 5
echo ""

# التأكد من أن السيرفر ما زال يعمل
if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo "❌ خطأ: السيرفر توقف بشكل غير متوقع!"
    echo "   جرب تشغل: python run.py (يدوياً لتشوف الأخطاء)"
    exit 1
fi

# الحصول على IP المحلي
LOCAL_IP=$(ip route get 1.1.1.1 2>/dev/null | grep -oP 'src \K\S+' | head -1)
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="127.0.0.1"
fi

echo "╔══════════════════════════════════════════════════════════╗"
echo "║                  ✅ السيرفر جاهز                          ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  🌐 محلي:            http://localhost:5001               ║"
echo "║  📱 شبكة محلية:      http://$LOCAL_IP:5001              ║"
echo "║  📁 مجلد المستخدمين: users/                              ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# تشغيل Cloudflare Tunnel (اختياري)
echo "🌍 هل تريد تشغيل Cloudflare Tunnel للوصول من الإنترنت؟"
echo "   (اضغط y للتشغيل، أو n للتخطي)"
read -n 1 RUN_TUNNEL
echo ""

if [[ "$RUN_TUNNEL" == "y" || "$RUN_TUNNEL" == "Y" ]]; then
    echo ""
    echo "🔄 جاري تشغيل Cloudflare Tunnel..."
    echo "   (اضغط Ctrl+C مرة وحدة لإيقاف الـ Tunnel، مرتين لإيقاف السيرفر)"
    echo ""
    
    # تشغيل tunnel
    cloudflared tunnel --url http://localhost:5001
    
    # لما يتوقف الـ tunnel، نسأل إذا بدو يوقف السيرفر كمان
    echo ""
    echo "🛑 Cloudflare Tunnel توقف"
    echo "   هل تريد إيقاف السيرفر أيضاً؟ (y/n)"
    read -n 1 STOP_SERVER
    echo ""
    
    if [[ "$STOP_SERVER" == "y" || "$STOP_SERVER" == "Y" ]]; then
        echo "🛑 جاري إيقاف السيرفر..."
        kill $SERVER_PID 2>/dev/null
        echo "✅ تم إيقاف السيرفر"
    else
        echo "ℹ️ السيرفر ما زال يعمل (PID: $SERVER_PID)"
        echo "   للإيقاف: kill $SERVER_PID"
    fi
else
    echo ""
    echo "ℹ️  تم تخطي Cloudflare Tunnel"
    echo "   السيرفر يعمل على الشبكة المحلية فقط"
    echo ""
    echo "🛑 لإيقاف السيرفر: kill $SERVER_PID"
    echo "   أو اضغط Ctrl+C"
    echo ""
    
    # الانتظار حتى يضغط المستخدم Ctrl+C
    wait $SERVER_PID
fi
