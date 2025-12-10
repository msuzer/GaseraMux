#!/bin/bash
set -e

DEVICE=${1:-/dev/sda}
PART=${DEVICE}1
LABEL="GASERADRIVE"
MOUNT_POINT="/media/usb0"
USER="www-data"

echo "=== USB FORMAT + AUTO-MOUNT SETUP ==="
echo
echo "Available devices:"
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,VENDOR,MODEL | grep -E "disk|NAME"
echo
echo "Device: $DEVICE"

# Check if device exists
if [ ! -b "$DEVICE" ]; then
    echo "ERROR: Device $DEVICE does not exist!"
    echo "Please specify the correct device as argument: $0 /dev/sdX"
    exit 1
fi

read -p "WARNING: This will erase $DEVICE. Continue? (yes/no): " yn
if [[ "$yn" != "yes" ]]; then
    echo "Aborted."
    exit 1
fi

echo ">>> Step 1: Unmounting old partition (ignore errors)"
sudo umount $PART 2>/dev/null || true

echo ">>> Step 2: Wiping filesystem signatures"
sudo wipefs -a $DEVICE

echo ">>> Step 3: Creating GPT partition table"
sudo parted -s $DEVICE mklabel gpt

echo ">>> Step 4: Creating ext4 partition (100%)"
sudo parted -s -a optimal $DEVICE mkpart primary ext4 0% 100%

echo ">>> Waiting for kernel to recognize new partition..."
sleep 2

echo ">>> Step 5: Formatting new partition as ext4"
sudo mkfs.ext4 -L $LABEL $PART

echo ">>> Step 6: Creating mount point"
sudo mkdir -p $MOUNT_POINT

echo ">>> Step 7: Mounting USB drive"
sudo mount $PART $MOUNT_POINT

echo ">>> Step 8: Creating logs folder"
sudo mkdir -p $MOUNT_POINT/logs
sudo chown -R $USER:$USER $MOUNT_POINT/logs
sudo chmod -R 775 $MOUNT_POINT/logs

echo ">>> Step 9: Adding /etc/fstab entry (safe, no boot failures)"
FSTAB_ENTRY="LABEL=$LABEL   $MOUNT_POINT   ext4   sync,noatime,nofail,x-systemd.automount   0   0"

# Remove any existing entry for this label or mount point
sudo sed -i "\|LABEL=$LABEL|d" /etc/fstab
sudo sed -i "\|$MOUNT_POINT|d" /etc/fstab

echo "$FSTAB_ENTRY" | sudo tee -a /etc/fstab > /dev/null

echo ">>> Step 10: Testing fstab"
sudo mount -a

echo ">>> Done!"
echo "USB drive is formatted, mounted, and configured for auto-mount on boot."
echo "If drive is missing at boot, system will NOT fail (thanks to nofail)."
