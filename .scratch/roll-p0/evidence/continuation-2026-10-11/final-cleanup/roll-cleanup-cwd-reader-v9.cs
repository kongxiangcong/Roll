using System;using System.Collections.Generic;using System.Runtime.InteropServices;using System.Text;
public sealed class CwdReadEvent { public string field;public int requested_bytes;public int actual_bytes;public bool succeeded; }
public sealed class CwdReadResult {public string state="UNKNOWN";public string reason;public string cwd;public bool reader_x64;public ushort process_machine;public ushort native_machine;public int nt_query_return_bytes;public List<CwdReadEvent> reads=new List<CwdReadEvent>();}
public static class ExactCwdReader {
 [StructLayout(LayoutKind.Sequential)] struct Basic { public IntPtr Reserved1,PebBaseAddress,Reserved2a,Reserved2b,UniqueProcessId,Reserved3; }
 [DllImport("kernel32.dll",SetLastError=true)]static extern IntPtr OpenProcess(uint access,bool inherit,int pid);
 [DllImport("kernel32.dll",SetLastError=true)]static extern bool IsWow64Process2(IntPtr h,out ushort pm,out ushort nm);
 [DllImport("kernel32.dll",SetLastError=true)]static extern bool ReadProcessMemory(IntPtr h,IntPtr a,[Out]byte[] b,UIntPtr count,out UIntPtr read);
 [DllImport("kernel32.dll")]static extern bool CloseHandle(IntPtr h);
 [DllImport("ntdll.dll")]static extern int NtQueryInformationProcess(IntPtr h,int c,out Basic b,int size,out int returned);
 static bool Pointer(long p){return p>0 && p<0x0000800000000000L && (p&7)==0;}
 static byte[] Read(IntPtr h,long a,int n,string field,CwdReadResult r){byte[] b=new byte[n];UIntPtr got;bool ok=ReadProcessMemory(h,new IntPtr(a),b,(UIntPtr)n,out got);int actual=(int)got.ToUInt64();r.reads.Add(new CwdReadEvent{field=field,requested_bytes=n,actual_bytes=actual,succeeded=ok&&actual==n});if(!ok||actual!=n)throw new InvalidOperationException("EXACT_READ_FAILED_"+field);return b;}
 public static CwdReadResult Get(int pid){var r=new CwdReadResult();r.reader_x64=IntPtr.Size==8;if(!r.reader_x64){r.reason="READER_NOT_X64";return r;}IntPtr h=OpenProcess(0x0400|0x1000|0x0010,false,pid);if(h==IntPtr.Zero){r.reason="OPEN_PROCESS_DENIED_"+Marshal.GetLastWin32Error();return r;}try{
  ushort pm,nm;if(!IsWow64Process2(h,out pm,out nm)){r.reason="ARCH_QUERY_FAILED_"+Marshal.GetLastWin32Error();return r;}r.process_machine=pm;r.native_machine=nm;if(pm!=0||nm!=0x8664){r.reason="TARGET_NOT_NATIVE_X64_FIXED_LAYOUT_REFUSED";return r;}
  Basic b;int returned;int status=NtQueryInformationProcess(h,0,out b,Marshal.SizeOf<Basic>(),out returned);r.nt_query_return_bytes=returned;if(status!=0||returned<48||b.UniqueProcessId.ToInt64()!=pid||!Pointer(b.PebBaseAddress.ToInt64())){r.reason="BASIC_INFO_LAYOUT_OR_ID_REFUSED";return r;}
  // Exactly x64 PEB.ProcessParameters pointer (+0x20), no other PEB fields.
  byte[] ptr=Read(h,b.PebBaseAddress.ToInt64()+0x20,8,"PEB.ProcessParameters_POINTER_8B",r);long pp=BitConverter.ToInt64(ptr,0);if(!Pointer(pp)){r.reason="PROCESS_PARAMETERS_POINTER_REFUSED";return r;}
  // Exactly RTL_USER_PROCESS_PARAMETERS.CurrentDirectory.DosPath (+0x38).
  byte[] us=Read(h,pp+0x38,16,"PARAMETERS.CurrentDirectory.DosPath_UNICODE_STRING_16B",r);int len=BitConverter.ToUInt16(us,0),max=BitConverter.ToUInt16(us,2);long buffer=BitConverter.ToInt64(us,8);
  if(len<=0||len>32768||(len&1)!=0||max<len||max>32768||(max&1)!=0||!Pointer(buffer)){r.reason="CWD_UNICODE_LENGTH_OR_POINTER_REFUSED";return r;}
  byte[] text=Read(h,buffer,len,"CurrentDirectory.DosPath_BUFFER_UTF16",r);string cwd=new UnicodeEncoding(false,false,true).GetString(text);if(cwd.IndexOf('\0')>=0){r.reason="CWD_EMBEDDED_NUL_REFUSED";return r;}r.cwd=cwd;r.state="CWD_EXACT_READ";r.reason="FIXED_X64_FIELDS_ONLY";return r;
 }catch(EntryPointNotFoundException){r.reason="ISWOW64PROCESS2_UNAVAILABLE_NO_LAYOUT_FALLBACK";return r;}catch(Exception e){r.reason=e is InvalidOperationException?e.Message:"CWD_READ_OR_UNICODE_VALIDATION_FAILED";return r;}finally{CloseHandle(h);}}
}
public static class CwdExactArgv {
 [DllImport("shell32.dll",SetLastError=true)]static extern IntPtr CommandLineToArgvW([MarshalAs(UnmanagedType.LPWStr)]string c,out int n);
 [DllImport("kernel32.dll")]static extern IntPtr LocalFree(IntPtr p);
 public static string[] Get(string c){int n;IntPtr p=CommandLineToArgvW(c,out n);if(p==IntPtr.Zero)return new string[0];try{var a=new string[n];for(int i=0;i<n;i++)a[i]=Marshal.PtrToStringUni(Marshal.ReadIntPtr(p,i*IntPtr.Size));return a;}finally{LocalFree(p);}}
}
