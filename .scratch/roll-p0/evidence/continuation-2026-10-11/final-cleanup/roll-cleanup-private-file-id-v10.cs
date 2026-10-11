// Public metadata-only helper. No ReadFile, file-content stream, ACL API, or process access.
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

namespace RollCleanupV10 {
    public sealed class Metadata {
        public string volume_serial { get; set; }
        public string file_id { get; set; }
        public ulong bytes { get; set; }
        public long mtime_ticks { get; set; }
        public uint attributes { get; set; }
        public uint number_of_links { get; set; }
    }
    public static class NativeMetadata {
        private const uint FILE_READ_ATTRIBUTES = 0x80;
        private const uint SHARE_READ_WRITE_DELETE = 7;
        private const uint OPEN_EXISTING = 3;
        private const uint FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000;
        private const uint FILE_FLAG_BACKUP_SEMANTICS = 0x02000000;
        private const uint FILE_ATTRIBUTE_REPARSE_POINT = 0x400;
        private const uint FILE_ATTRIBUTE_DIRECTORY = 0x10;
        [StructLayout(LayoutKind.Sequential)]
        private struct FILETIME { public uint Low; public uint High; }
        [StructLayout(LayoutKind.Sequential)]
        private struct BY_HANDLE_FILE_INFORMATION {
            public uint Attributes;
            public FILETIME CreationTime;
            public FILETIME LastAccessTime;
            public FILETIME LastWriteTime;
            public uint VolumeSerialNumber;
            public uint FileSizeHigh;
            public uint FileSizeLow;
            public uint NumberOfLinks;
            public uint FileIndexHigh;
            public uint FileIndexLow;
        }
        [DllImport("kernel32.dll", CharSet=CharSet.Unicode, ExactSpelling=true, SetLastError=true)]
        private static extern SafeFileHandle CreateFileW(string path, uint access, uint share,
            IntPtr security, uint creation, uint flags, IntPtr template);
        [DllImport("kernel32.dll", ExactSpelling=true, SetLastError=true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool GetFileInformationByHandle(SafeFileHandle handle,
            out BY_HANDLE_FILE_INFORMATION info);
        public static Metadata File(string path) { return Query(path, false); }
        public static Metadata Directory(string path) { return Query(path, true); }
        private static Metadata Query(string path, bool directory) {
            if (String.IsNullOrWhiteSpace(path) || !System.IO.Path.IsPathFullyQualified(path))
                throw new ArgumentException("Exact absolute metadata path required");
            using (SafeFileHandle handle = CreateFileW(path, FILE_READ_ATTRIBUTES,
                SHARE_READ_WRITE_DELETE, IntPtr.Zero, OPEN_EXISTING,
                FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS, IntPtr.Zero)) {
                if (handle.IsInvalid) throw new Win32Exception(Marshal.GetLastWin32Error());
                BY_HANDLE_FILE_INFORMATION info;
                if (!GetFileInformationByHandle(handle, out info))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                if ((info.Attributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0)
                    throw new InvalidOperationException("Reparse metadata endpoint refused");
                if (((info.Attributes & FILE_ATTRIBUTE_DIRECTORY) != 0) != directory)
                    throw new InvalidOperationException("Regular file/directory type differs");
                ulong fileIndex = ((ulong)info.FileIndexHigh << 32) | info.FileIndexLow;
                ulong time = ((ulong)info.LastWriteTime.High << 32) | info.LastWriteTime.Low;
                return new Metadata {
                    volume_serial = info.VolumeSerialNumber.ToString("x8"),
                    file_id = fileIndex.ToString("x16"),
                    bytes = ((ulong)info.FileSizeHigh << 32) | info.FileSizeLow,
                    mtime_ticks = DateTime.FromFileTimeUtc(checked((long)time)).Ticks,
                    attributes = info.Attributes,
                    number_of_links = info.NumberOfLinks
                };
            }
        }
    }
}
